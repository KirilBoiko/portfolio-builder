import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Builder",
    page_icon="🚀",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ---- global ---- */
    html, body, [data-testid="stAppViewContainer"] {
        background: #0f1117;
        color: #e6edf3;
        font-family: 'Inter', sans-serif;
    }

    /* ---- card wrapper ---- */
    .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 2rem 2.25rem;
        margin-bottom: 1.5rem;
    }

    /* ---- section headings ---- */
    .section-title {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b949e;
        margin-bottom: 0.75rem;
    }

    /* ---- inputs & text areas ---- */
    input, textarea {
        background: #0d1117 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        color: #e6edf3 !important;
    }
    input:focus, textarea:focus {
        border-color: #58a6ff !important;
        box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15) !important;
    }

    /* ---- deploy button ---- */
    div[data-testid="stButton"] > button {
        width: 100%;
        padding: 0.85rem 0;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: #ffffff;
        cursor: pointer;
        transition: filter 0.2s ease, transform 0.1s ease;
    }
    div[data-testid="stButton"] > button:hover {
        filter: brightness(1.12);
        transform: translateY(-1px);
    }
    div[data-testid="stButton"] > button:active {
        transform: translateY(0);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 🚀 Portfolio Builder")
st.markdown(
    "<p style='color:#8b949e; margin-top:-0.5rem; margin-bottom:1.5rem;'>"
    "Fill in the details below and we'll generate &amp; deploy your personal portfolio site."
    "</p>",
    unsafe_allow_html=True,
)

# ── Section 1: API Keys ────────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<p class="section-title">🔑 API Keys</p>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    llm_api_key = st.text_input(
        "LLM API Key",
        type="password",
        placeholder="sk-…",
        help="Your OpenAI / Gemini / Anthropic API key",
        key="llm_api_key",
    )
with col2:
    github_token = st.text_input(
        "GitHub Token",
        type="password",
        placeholder="ghp_…",
        help="A GitHub Personal Access Token with repo + pages scopes",
        key="github_token",
    )

st.markdown("</div>", unsafe_allow_html=True)

# ── Section 2: About You ───────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<p class="section-title">👤 About You</p>', unsafe_allow_html=True)

user_bio = st.text_area(
    "Bio",
    placeholder="Write a short bio — who you are, what you do, and what you're passionate about…",
    height=130,
    key="user_bio",
)

user_links = st.text_area(
    "Links",
    placeholder="Paste your links here, one per line:\nhttps://github.com/you\nhttps://linkedin.com/in/you\nhttps://yoursite.com",
    height=120,
    key="user_links",
)

st.markdown("</div>", unsafe_allow_html=True)

# ── Section 3: Portfolio Aesthetic ────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<p class="section-title">🎨 Portfolio Aesthetic</p>', unsafe_allow_html=True)

aesthetic_col1, aesthetic_col2 = st.columns(2)
with aesthetic_col1:
    color_theme = st.selectbox(
        "Color Theme",
        ["Dark & Minimal", "Light & Clean", "Cyberpunk", "Earthy Tones", "Ocean Blue"],
        key="color_theme",
    )
with aesthetic_col2:
    layout_style = st.selectbox(
        "Layout Style",
        ["Single Page", "Multi-Section Scroll", "Grid Gallery", "Timeline"],
        key="layout_style",
    )

aesthetic_notes = st.text_area(
    "Additional Aesthetic Notes",
    placeholder="Describe the vibe you're going for — fonts, mood, inspirations, anything that helps…",
    height=100,
    key="aesthetic_notes",
)

st.markdown("</div>", unsafe_allow_html=True)

# ── Build & Deploy Button ──────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀  Build & Deploy", key="build_deploy_btn"):
    # ── Validation ────────────────────────────────────────────────────────────
    missing = []
    if not llm_api_key:
        missing.append("LLM API Key")
    if not github_token:
        missing.append("GitHub Token")
    if not user_bio:
        missing.append("Bio")

    if missing:
        st.error(f"Please fill in the following required fields: **{', '.join(missing)}**")
    else:
        from backend import generate_portfolio, deploy_to_github

        user_data = {
            "bio": user_bio, "links": user_links,
            "color_theme": color_theme, "layout_style": layout_style,
            "aesthetic_notes": aesthetic_notes,
            }
        html = generate_portfolio(llm_api_key, user_data)
        pages_url = deploy_to_github(github_token, html)
        st.success(f"🎉 Live at [{pages_url}]({pages_url})")
