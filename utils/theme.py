"""
utils/theme.py
----------------
Centralized visual theme for the Streamlit app: custom CSS injection,
a branded header, and small styled-component helpers (status pills,
metric cards) so every page looks consistent instead of default
Streamlit gray-and-red.

Import and call `inject_custom_css()` once near the top of app.py, and
`render_header()` right after `st.set_page_config`.
"""

import streamlit as st

PRIMARY = "#0A66C2"       # LinkedIn blue -- ties the brand to the platform it publishes to
PRIMARY_DARK = "#004182"
ACCENT_BG = "#EAF3FC"
SUCCESS = "#0F9D58"
WARNING = "#B45309"
DANGER = "#D93025"
TEXT_MUTED = "#5F6368"


def inject_custom_css():
    st.markdown(
        f"""
        <style>
        /* ---------- Global type & spacing ---------- */
        html, body, [class*="css"] {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }}

        /* ---------- Hide default Streamlit chrome ---------- */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {{
            background-color: #F7F9FA;
            border-right: 1px solid #E1E4E8;
        }}
        section[data-testid="stSidebar"] .stRadio > label {{
            font-weight: 600;
        }}

        /* ---------- Buttons ---------- */
        .stButton > button {{
            border-radius: 8px;
            border: 1px solid #D0D5DA;
            font-weight: 500;
            transition: all 0.15s ease;
        }}
        .stButton > button:hover {{
            border-color: {PRIMARY};
            color: {PRIMARY};
        }}
        .stButton > button[kind="primary"] {{
            background-color: {PRIMARY};
            border-color: {PRIMARY};
        }}
        .stButton > button[kind="primary"]:hover {{
            background-color: {PRIMARY_DARK};
            border-color: {PRIMARY_DARK};
            color: white;
        }}

        /* ---------- Tabs ---------- */
        .stTabs [data-baseweb="tab"] {{
            font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{
            color: {PRIMARY};
        }}

        /* ---------- Headings ---------- */
        h1, h2, h3 {{
            font-weight: 700;
            letter-spacing: -0.01em;
        }}

        /* ---------- Custom card ---------- */
        .app-card {{
            background: white;
            border: 1px solid #E1E4E8;
            border-radius: 12px;
            padding: 1.1rem 1.3rem;
            margin-bottom: 0.75rem;
        }}
        .app-card:hover {{
            border-color: {PRIMARY};
        }}

        /* ---------- Status pills ---------- */
        .pill {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .pill-success {{ background: #E6F4EA; color: {SUCCESS}; }}
        .pill-warning {{ background: #FDF3E7; color: {WARNING}; }}
        .pill-danger  {{ background: #FCE8E6; color: {DANGER}; }}
        .pill-muted   {{ background: #F1F3F4; color: {TEXT_MUTED}; }}

        /* ---------- Header banner ---------- */
        .app-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
            border-bottom: 1px solid #E1E4E8;
        }}
        .app-header .logo-badge {{
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: {PRIMARY};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
            flex-shrink: 0;
        }}
        .app-header .title {{
            font-size: 20px;
            font-weight: 700;
            margin: 0;
            line-height: 1.2;
        }}
        .app-header .subtitle {{
            font-size: 13px;
            color: {TEXT_MUTED};
            margin: 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(workspace_name: str = None):
    subtitle = f"Managing content for {workspace_name}" if workspace_name else "Multi-company LinkedIn content strategist"
    st.markdown(
        f"""
        <div class="app-header">
            <div class="logo-badge">in</div>
            <div>
                <p class="title">LinkedIn AI Strategist</p>
                <p class="subtitle">{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(text: str, kind: str = "muted") -> str:
    """kind: success | warning | danger | muted. Returns HTML -- render with st.markdown(..., unsafe_allow_html=True)."""
    return f'<span class="pill pill-{kind}">{text}</span>'
