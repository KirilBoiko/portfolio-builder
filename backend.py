"""
backend.py — Portfolio Builder core engine
==========================================
Exports two public functions consumed by app.py:

    generate_portfolio(api_key, user_data)  -> str  (raw HTML)
    deploy_to_github(github_token, html_code) -> str  (GitHub Pages URL)

All heavy network calls are isolated here so the Streamlit frontend stays
thin and free of business logic.
"""

from __future__ import annotations

import re
import time
from typing import Any

# ── Gemini SDK ─────────────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "google-generativeai is not installed. "
        "Run: pip install google-generativeai"
    ) from exc

# ── PyGithub ───────────────────────────────────────────────────────────────────
try:
    from github import Github, GithubException, InputGitTreeElement
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyGithub is not installed. "
        "Run: pip install PyGithub"
    ) from exc


# ══════════════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════════════

# Gemini model to use for generation.
# gemini-1.5-pro gives the richest HTML; swap to gemini-1.5-flash for speed.
GEMINI_MODEL = "gemini-2.0-flash"

# Maximum tokens the model is allowed to produce (one-file HTML can be large).
MAX_OUTPUT_TOKENS = 8192

# Name of the GitHub repository that will be created / reused.
REPO_NAME_PREFIX = "portfolio-builder"

# Branch that GitHub Pages serves from.
PAGES_BRANCH = "main"

# Commit message used when pushing index.html.
COMMIT_MESSAGE = "🚀 Deploy portfolio via Portfolio Builder"


# ══════════════════════════════════════════════════════════════════════════════
#  1. generate_portfolio
# ══════════════════════════════════════════════════════════════════════════════

def generate_portfolio(api_key: str, user_data: dict[str, Any]) -> str:
    """
    Call the Gemini API to generate a self-contained HTML portfolio file.

    Parameters
    ----------
    api_key : str
        A valid Google Gemini API key.
    user_data : dict
        Keys expected:
            bio             (str)  – Short personal bio.
            links           (str)  – Newline-separated URLs.
            color_theme     (str)  – E.g. "Dark & Minimal", "Cyberpunk", …
            layout_style    (str)  – E.g. "Single Page", "Timeline", …
            aesthetic_notes (str)  – Free-form additional style notes.

    Returns
    -------
    str
        Raw HTML string ready to be written to index.html.

    Raises
    ------
    ValueError
        If the API key is empty or the model returns no usable content.
    RuntimeError
        If the Gemini API call itself fails (network error, quota, etc.).
    """

    # ── Guard: empty key ───────────────────────────────────────────────────────
    if not api_key or not api_key.strip():
        raise ValueError("Gemini API key must not be empty.")

    # ── Configure the SDK with the caller-supplied key ─────────────────────────
    genai.configure(api_key=api_key.strip())

    # ── Build the system prompt ────────────────────────────────────────────────
    system_prompt = (
        "You are an expert front-end developer who writes stunning, award-winning "
        "portfolio websites. You output ONLY raw, valid HTML — no markdown fences, "
        "no explanatory text, no preamble. The HTML must be entirely self-contained "
        "(all CSS and JS inline, no external stylesheets except Google Fonts CDN "
        "and Tailwind CDN). The page must be mobile-responsive and accessible."
    )

    # ── Build the user prompt from the form data ───────────────────────────────
    links_formatted = "\n".join(
        f"  • {url.strip()}"
        for url in user_data.get("links", "").splitlines()
        if url.strip()
    ) or "  (none provided)"

    user_prompt = f"""
Create a complete, single-file HTML portfolio website for the following person.

=== BIO ===
{user_data.get("bio", "").strip()}

=== LINKS ===
{links_formatted}

=== DESIGN PREFERENCES ===
Color Theme  : {user_data.get("color_theme", "Dark & Minimal")}
Layout Style : {user_data.get("layout_style", "Single Page")}
Extra Notes  : {user_data.get("aesthetic_notes", "").strip() or "(none)"}

=== REQUIREMENTS ===
1. Use Tailwind CSS (CDN) for utility classes.
2. Add tasteful CSS animations / transitions (scroll-reveal, hover effects).
3. Include a hero section, about section, links/contact section.
4. All images should be replaced with elegant SVG illustrations or CSS art —
   do not embed base64 blobs.
5. Output ONLY the HTML — nothing else.
""".strip()

    # ── Call Gemini ────────────────────────────────────────────────────────────
    try:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.7,
            ),
        )
        response = model.generate_content(user_prompt)
    except Exception as exc:
        raise RuntimeError(
            f"Gemini API call failed: {exc}\n"
            "Check your API key, quota, and network connection."
        ) from exc

    # ── Extract the text safely ────────────────────────────────────────────────
    try:
        raw_text: str = response.text
    except Exception as exc:
        raise ValueError(
            f"Gemini returned no usable content. "
            f"Finish reason: {response.candidates[0].finish_reason if response.candidates else 'unknown'}. "
            f"Detail: {exc}"
        ) from exc

    # ── Strip accidental markdown fences the model may add ────────────────────
    html = _strip_markdown_fences(raw_text)

    if not html.strip():
        raise ValueError("Gemini returned an empty HTML response.")

    return html


def _strip_markdown_fences(text: str) -> str:
    """
    Remove ```html … ``` or ``` … ``` wrappers that the model sometimes adds
    despite instructions to the contrary.
    """
    # Match opening fence with optional language tag, content, closing fence
    pattern = r"^```[a-zA-Z]*\n([\s\S]*?)```\s*$"
    match = re.match(pattern, text.strip())
    if match:
        return match.group(1)
    return text


# ══════════════════════════════════════════════════════════════════════════════
#  2. deploy_to_github
# ══════════════════════════════════════════════════════════════════════════════

def deploy_to_github(github_token: str, html_code: str) -> str:
    """
    Create (or reuse) a public GitHub repository and push index.html so that
    GitHub Pages serves the portfolio at https://<user>.github.io/<repo>/.

    Parameters
    ----------
    github_token : str
        A GitHub Personal Access Token with `repo` scope.
        For GitHub Pages on a new repo, the token also needs the `pages` scope
        (or the user can enable Pages manually after the push).
    html_code : str
        The raw HTML string to write as index.html.

    Returns
    -------
    str
        The expected GitHub Pages URL for the deployed portfolio.

    Raises
    ------
    ValueError
        If the token is empty or html_code is blank.
    PermissionError
        If the token does not have sufficient scopes.
    RuntimeError
        If any GitHub API call fails unexpectedly.
    """

    # ── Guard: empty inputs ────────────────────────────────────────────────────
    if not github_token or not github_token.strip():
        raise ValueError("GitHub token must not be empty.")
    if not html_code or not html_code.strip():
        raise ValueError("html_code must not be empty.")

    # ── Authenticate ───────────────────────────────────────────────────────────
    try:
        gh = Github(github_token.strip())
        auth_user = gh.get_user()
        username = auth_user.login  # triggers the actual API call / auth check
    except GithubException as exc:
        if exc.status == 401:
            raise PermissionError(
                "GitHub token is invalid or expired (401 Unauthorized)."
            ) from exc
        raise RuntimeError(f"GitHub authentication failed: {exc}") from exc

    # ── Determine a unique repo name ───────────────────────────────────────────
    repo_name = _unique_repo_name(auth_user, REPO_NAME_PREFIX)

    # ── Create the repository ──────────────────────────────────────────────────
    try:
        repo = auth_user.create_repo(
            name=repo_name,
            description="✨ Personal portfolio — generated by Portfolio Builder",
            homepage=f"https://{username}.github.io/{repo_name}/",
            private=False,
            auto_init=True,       # creates an initial commit so the branch exists
            gitignore_template=None,
            license_template=None,
        )
    except GithubException as exc:
        if exc.status == 422:
            raise RuntimeError(
                f"Repository '{repo_name}' already exists or the name is invalid: {exc.data}"
            ) from exc
        raise RuntimeError(f"Failed to create repository: {exc}") from exc

    # ── GitHub needs a moment after auto_init before we can push ──────────────
    time.sleep(2)

    # ── Push index.html ────────────────────────────────────────────────────────
    try:
        _push_file(
            repo=repo,
            file_path="index.html",
            content=html_code,
            commit_message=COMMIT_MESSAGE,
            branch=PAGES_BRANCH,
        )
    except GithubException as exc:
        raise RuntimeError(f"Failed to push index.html: {exc}") from exc

    # ── Enable GitHub Pages (source = root of main branch) ────────────────────
    try:
        repo.enable_pages(source={"branch": PAGES_BRANCH, "path": "/"})
    except GithubException as exc:
        # Pages enablement can sometimes fail on fresh repos or token scope issues.
        # We still return the expected URL — the user can enable Pages manually.
        pages_url = f"https://{username}.github.io/{repo_name}/"
        print(
            f"[Warning] Could not automatically enable GitHub Pages: {exc}\n"
            f"Please enable it manually at: {repo.html_url}/settings/pages\n"
            f"Expected URL once enabled: {pages_url}"
        )
        return pages_url

    # ── Return the live Pages URL ──────────────────────────────────────────────
    pages_url = f"https://{username}.github.io/{repo_name}/"
    return pages_url


# ── Helpers ────────────────────────────────────────────────────────────────────

def _unique_repo_name(auth_user: Any, prefix: str) -> str:
    """
    Return `prefix` if no repo with that name exists, otherwise append -2, -3, …
    until a free name is found (max 99 attempts).
    """
    existing_names = {r.name for r in auth_user.get_repos()}
    candidate = prefix
    for i in range(2, 100):
        if candidate not in existing_names:
            return candidate
        candidate = f"{prefix}-{i}"
    # Extremely unlikely; fall back to a timestamped name
    return f"{prefix}-{int(time.time())}"


def _push_file(
    repo: Any,
    file_path: str,
    content: str,
    commit_message: str,
    branch: str,
) -> None:
    """
    Create or update `file_path` in `repo` on `branch` with `content`.
    Uses the Contents API (works for files up to ~1 MB).
    """
    try:
        # Check if the file already exists (e.g., if repo was reused)
        existing = repo.get_contents(file_path, ref=branch)
        repo.update_file(
            path=file_path,
            message=commit_message,
            content=content,
            sha=existing.sha,
            branch=branch,
        )
    except GithubException as exc:
        if exc.status == 404:
            # File doesn't exist yet — create it
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch,
            )
        else:
            raise
