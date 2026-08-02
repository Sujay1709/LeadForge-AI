"""
LeadForge AI — Copilot-style Lead Generation Platform
Run with: streamlit run app.py
"""

import time
import json
import requests
import streamlit as st
import pandas as pd
from datetime import datetime

from config import (
    get_api_keys, get_validated_keys, DEFAULT_NUM_LINKS, DEFAULT_MODEL,
    AVAILABLE_SOURCES, search_limiter, PIPELINE_STAGES, PIPELINE_COLORS,
)
from scraper import search_for_urls, extract_user_info_from_urls, format_leads_to_flat_json
from agents import (
    create_prompt_transform_agent, transform_query, write_to_google_sheets,
    enrich_leads_batch,
)
from tools import research_topic

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page Config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="LeadForge AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Custom CSS — Copilot-inspired dark UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* ── Global ── */
    .stApp { background: #0a0a0a; font-family: 'Inter', sans-serif; }
    header[data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }
    * { -webkit-tap-highlight-color: transparent; }

    /* ── Sidebar — Copilot style ── */
    section[data-testid="stSidebar"] {
        background: #0d0d0d; border-right: 1px solid #1a1a1a;
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h3 { color: #c6ff00 !important; font-size: 0.8rem !important; text-transform: uppercase; letter-spacing: 0.08em; }

    /* ── Logo mark ── */
    .logo-mark {
        display: flex; align-items: center; gap: 12px;
        padding: 20px 8px 16px; border-bottom: 1px solid #1a1a1a; margin-bottom: 16px;
    }
    .logo-icon {
        width: 40px; height: 40px; border-radius: 12px;
        background: linear-gradient(135deg, #c6ff00, #00e676);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.2rem; flex-shrink: 0;
    }
    .logo-text { font-size: 1.1rem; font-weight: 800; color: #eee; }
    .logo-sub { font-size: 0.65rem; color: #555; margin-top: 2px; }

    /* ── Pinned & Recent sections ── */
    .section-label {
        font-size: 0.65rem; font-weight: 600; color: #555;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 16px 0 8px; padding: 0 4px;
    }

    /* ── Lead list item (sidebar) ── */
    .lead-list-item {
        padding: 10px 12px; margin: 4px 0; background: #111;
        border: 1px solid #1a1a1a; border-radius: 10px;
        cursor: pointer; transition: all 0.15s cubic-bezier(.4,0,.2,1);
    }
    .lead-list-item:hover { border-color: #333; background: #151515; transform: translateX(2px); }
    .lead-list-item:active { transform: scale(0.98); }
    .lead-list-item.pinned { border-left: 3px solid #c6ff00; }
    .lead-item-title { font-size: 0.82rem; font-weight: 600; color: #ddd; }
    .lead-item-meta { font-size: 0.68rem; color: #666; margin-top: 3px; }
    .lead-item-count {
        display: inline-block; padding: 2px 8px; border-radius: 6px;
        background: rgba(198,255,0,0.1); color: #c6ff00;
        font-size: 0.65rem; font-weight: 600; margin-left: 4px;
    }

    /* ── Main content area ── */
    .main-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 0 20px; border-bottom: 1px solid #1a1a1a; margin-bottom: 20px;
    }
    .main-title { font-size: 1.5rem; font-weight: 800; color: #eee; }

    /* ── Step indicators (chat-like) ── */
    .step-row {
        display: flex; align-items: flex-start; gap: 12px;
        padding: 12px 0; border-bottom: 1px solid #0f0f0f;
    }
    .step-icon {
        width: 28px; height: 28px; border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8rem; flex-shrink: 0; margin-top: 2px;
    }
    .step-icon.done { background: rgba(198,255,0,0.15); }
    .step-icon.working { background: rgba(255,171,0,0.15); }
    .step-icon.error { background: rgba(255,82,82,0.15); }
    .step-text { font-size: 0.88rem; color: #bbb; line-height: 1.5; }
    .step-text strong { color: #eee; }

    /* ── Lead results table ── */
    .results-header {
        display: flex; align-items: center; gap: 12px;
        padding: 14px 16px; background: #111; border: 1px solid #1a1a1a;
        border-radius: 12px 12px 0 0; margin-top: 20px;
    }
    .results-title { font-size: 0.95rem; font-weight: 700; color: #eee; }
    .results-badge {
        padding: 3px 10px; border-radius: 6px;
        background: rgba(198,255,0,0.12); color: #c6ff00;
        font-size: 0.7rem; font-weight: 600;
    }

    /* ── Source tags ── */
    .source-tag {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 10px; border-radius: 6px;
        font-size: 0.68rem; font-weight: 600;
    }
    .source-quora { background: rgba(185,43,39,0.15); color: #e74c3c; }
    .source-pinterest { background: rgba(189,8,28,0.15); color: #e60023; }

    /* ── Metric cards ── */
    .metric-row { display: flex; gap: 12px; margin: 1rem 0; }
    .metric-card {
        flex: 1; background: #111; border: 1px solid #1a1a1a;
        border-radius: 12px; padding: 16px; text-align: center;
        transition: all 0.2s cubic-bezier(.4,0,.2,1);
    }
    .metric-card:hover { border-color: #333; transform: translateY(-2px); }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #c6ff00; }
    .metric-label { font-size: 0.68rem; color: #555; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }

    /* ── Search input area ── */
    .stTextArea textarea {
        background: #111 !important; border: 1px solid #222 !important;
        color: #eee !important; border-radius: 12px !important;
        font-size: 0.95rem !important;
    }
    .stTextArea textarea:focus {
        border-color: #c6ff00 !important;
        box-shadow: 0 0 0 2px rgba(198,255,0,0.08) !important;
    }
    .stTextInput input {
        background: #111 !important; border: 1px solid #222 !important;
        color: #eee !important; border-radius: 10px !important;
    }

    /* ── Primary action buttons (Generate, Enrich, etc.) ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #c6ff00, #76ff03) !important;
        color: #000 !important; font-weight: 700 !important;
        border: none !important; border-radius: 12px !important;
        padding: 0.6rem 1.8rem !important; font-size: 0.95rem !important;
        transition: all 0.15s cubic-bezier(.4,0,.2,1) !important;
        box-shadow: 0 2px 8px rgba(198,255,0,0.15) !important;
        position: relative; overflow: hidden;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 6px 20px rgba(198,255,0,0.3) !important;
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(1px) scale(0.96) !important;
        box-shadow: 0 1px 4px rgba(198,255,0,0.15) !important;
        transition: all 0.06s !important;
    }

    /* ── Secondary / Nav buttons ── */
    .stButton > button[kind="secondary"],
    .stButton > button:not([kind="primary"]):not([kind]) {
        background: #111 !important; border: 1px solid #1a1a1a !important;
        color: #888 !important; font-weight: 600 !important;
        border-radius: 8px !important; font-size: 0.78rem !important;
        padding: 0.45rem 1rem !important;
        box-shadow: none !important;
        transition: all 0.15s cubic-bezier(.4,0,.2,1) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button:not([kind="primary"]):not([kind]):hover {
        border-color: #c6ff00 !important; color: #c6ff00 !important;
        background: #151515 !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"]:active,
    .stButton > button:not([kind="primary"]):not([kind]):active {
        transform: scale(0.97) !important;
    }

    /* ── Download buttons ── */
    .stDownloadButton > button {
        background: #111 !important; border: 1px solid #222 !important;
        color: #c6ff00 !important; border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.15s cubic-bezier(.4,0,.2,1) !important;
    }
    .stDownloadButton > button:hover {
        border-color: #c6ff00 !important; background: #151515 !important;
        transform: translateY(-1px) !important;
    }
    .stDownloadButton > button:active {
        transform: translateY(1px) scale(0.97) !important;
    }

    /* ── Sidebar buttons ── */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important; border: 1px solid #222 !important;
        color: #888 !important; font-size: 0.72rem !important;
        padding: 0.25rem 0.6rem !important; box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: #ff5252 !important; color: #ff5252 !important;
        background: rgba(255,82,82,0.06) !important;
    }

    /* ── Multiselect / selectbox ── */
    .stMultiSelect > div > div, .stSelectbox > div > div {
        background: #111 !important; border-color: #222 !important;
    }

    /* ── Slider ── */
    .stSlider [data-baseweb="slider"] [role="slider"] { background: #c6ff00 !important; }

    /* ── Toggle ── */
    .stToggle label span { transition: all 0.2s !important; }

    /* ── File uploader ── */
    .stFileUploader > div { border-radius: 12px !important; }

    /* ── Error / warning ── */
    .error-banner {
        padding: 12px 16px; border-radius: 10px;
        background: rgba(255,82,82,0.08); border: 1px solid rgba(255,82,82,0.2);
        color: #ff8a80; font-size: 0.85rem; margin: 8px 0;
    }
    .warning-banner {
        padding: 12px 16px; border-radius: 10px;
        background: rgba(255,171,0,0.08); border: 1px solid rgba(255,171,0,0.2);
        color: #ffcc80; font-size: 0.85rem; margin: 8px 0;
    }

    /* ── Footer ── */
    .app-footer {
        text-align: center; color: #222; font-size: 0.65rem;
        padding: 24px 0 12px; border-top: 1px solid #111; margin-top: 40px;
    }

    /* ── Speed stats ── */
    .speed-stat {
        font-size: 0.8rem; color: #76ff03; font-weight: 600;
        padding: 5px 12px; background: rgba(118,255,3,0.06);
        border-radius: 8px; display: inline-block; margin: 3px;
    }

    /* ── API status card ── */
    .api-card {
        background: #111; border: 1px solid #1a1a1a; border-radius: 10px;
        padding: 12px; margin: 6px 0;
    }
    .api-name { font-size: 0.78rem; font-weight: 700; color: #ccc; }
    .api-desc { font-size: 0.68rem; color: #555; line-height: 1.4; margin-top: 3px; }
    .api-status { font-size: 0.65rem; font-weight: 600; margin-top: 5px; }

    /* ── Enrichment badge ── */
    .enrich-badge {
        display: inline-block; padding: 2px 8px; border-radius: 6px;
        font-size: 0.65rem; font-weight: 600;
    }
    .enrich-hot { background: rgba(255,82,82,0.15); color: #ff5252; }
    .enrich-warm { background: rgba(255,171,0,0.15); color: #ffab00; }
    .enrich-cold { background: rgba(74,158,255,0.15); color: #4a9eff; }

    hr { border-color: #1a1a1a !important; }

    /* ━━━━━━ Landing Page Styles ━━━━━━ */
    .landing-nav {
        display: flex; align-items: center; justify-content: space-between;
        padding: 18px 48px; position: fixed; top: 0; left: 0; right: 0;
        z-index: 9999; background: rgba(10,10,10,0.85);
        backdrop-filter: blur(20px); border-bottom: 1px solid #1a1a1a;
    }
    .landing-nav-logo {
        font-size: 1.4rem; font-weight: 900; color: #fff;
        display: flex; align-items: center; gap: 8px;
    }
    .landing-nav-logo .dot { color: #4a9eff; }
    .landing-nav-links { display: flex; align-items: center; gap: 32px; }
    .landing-nav-links a {
        color: #999; text-decoration: none; font-size: 0.88rem;
        font-weight: 500; transition: color 0.2s;
    }
    .landing-nav-links a:hover { color: #fff; }
    .landing-nav-cta {
        padding: 10px 24px; border-radius: 8px; font-weight: 600;
        font-size: 0.88rem; text-decoration: none; transition: all 0.2s;
    }
    .nav-signin { color: #ccc !important; }
    .nav-trial {
        background: #4a9eff !important; color: #fff !important;
        border: none;
    }
    .nav-trial:hover { background: #3b8de8 !important; transform: translateY(-1px); }

    .landing-hero {
        text-align: center; padding: 160px 20px 80px;
        background: radial-gradient(ellipse at 50% 0%, rgba(74,158,255,0.08) 0%, transparent 60%);
    }
    .landing-badge {
        display: inline-flex; align-items: center; gap: 8px;
        padding: 8px 20px; border-radius: 24px;
        border: 1px solid rgba(74,158,255,0.25); color: #4a9eff;
        font-size: 0.82rem; font-weight: 500; margin-bottom: 32px;
    }
    .landing-h1 {
        font-size: 4rem; font-weight: 900; color: #fff;
        line-height: 1.1; margin-bottom: 24px; letter-spacing: -0.03em;
    }
    .landing-h1 .highlight { color: #4a9eff; }
    .landing-sub {
        font-size: 1.15rem; color: #777; max-width: 600px;
        margin: 0 auto 48px; line-height: 1.7;
    }
    .landing-ctas {
        display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
    }
    .landing-ctas a, .landing-ctas button {
        padding: 16px 36px; border-radius: 10px; font-size: 1rem;
        font-weight: 600; text-decoration: none; transition: all 0.2s;
        cursor: pointer; border: none;
    }
    .cta-primary {
        background: #4a9eff; color: #fff !important;
        box-shadow: 0 4px 20px rgba(74,158,255,0.25);
    }
    .cta-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(74,158,255,0.35); }
    .cta-secondary {
        background: transparent; color: #ccc !important;
        border: 1px solid #333 !important;
    }
    .cta-secondary:hover { border-color: #555 !important; color: #fff !important; }

    .landing-section {
        padding: 80px 48px; max-width: 1200px; margin: 0 auto;
    }
    .landing-section-title {
        font-size: 2.2rem; font-weight: 800; color: #fff;
        text-align: center; margin-bottom: 12px;
    }
    .landing-section-sub {
        font-size: 1rem; color: #666; text-align: center;
        margin-bottom: 56px; max-width: 600px; margin-left: auto; margin-right: auto;
    }

    .feature-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 24px; margin-bottom: 40px;
    }
    .feature-card {
        background: #111; border: 1px solid #1a1a1a; border-radius: 16px;
        padding: 32px; transition: all 0.25s;
    }
    .feature-card:hover { border-color: #4a9eff; transform: translateY(-4px); box-shadow: 0 8px 30px rgba(74,158,255,0.08); }
    .feature-icon {
        width: 48px; height: 48px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.5rem; margin-bottom: 20px;
        background: rgba(74,158,255,0.1);
    }
    .feature-card h3 { font-size: 1.1rem; font-weight: 700; color: #eee; margin-bottom: 8px; }
    .feature-card p { font-size: 0.88rem; color: #666; line-height: 1.6; }

    .audience-grid {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;
    }
    .audience-card {
        background: #111; border: 1px solid #1a1a1a; border-radius: 14px;
        padding: 28px 20px; text-align: center; transition: all 0.25s;
    }
    .audience-card:hover { border-color: #333; transform: translateY(-3px); }
    .audience-icon { font-size: 2.2rem; margin-bottom: 14px; }
    .audience-card h4 { font-size: 0.95rem; font-weight: 700; color: #ddd; margin-bottom: 6px; }
    .audience-card p { font-size: 0.78rem; color: #555; line-height: 1.5; }

    .creator-section {
        display: flex; align-items: center; gap: 48px;
        background: #111; border: 1px solid #1a1a1a; border-radius: 20px;
        padding: 48px; margin: 0 auto; max-width: 800px;
    }
    .creator-avatar {
        width: 100px; height: 100px; border-radius: 50%;
        background: linear-gradient(135deg, #4a9eff, #00e676);
        display: flex; align-items: center; justify-content: center;
        font-size: 2.5rem; flex-shrink: 0;
    }
    .creator-info h3 { font-size: 1.3rem; font-weight: 800; color: #eee; margin-bottom: 4px; }
    .creator-info .role { font-size: 0.88rem; color: #4a9eff; font-weight: 600; margin-bottom: 12px; }
    .creator-info p { font-size: 0.9rem; color: #777; line-height: 1.7; }

    .landing-footer {
        text-align: center; padding: 48px; border-top: 1px solid #1a1a1a;
        color: #333; font-size: 0.78rem; margin-top: 40px;
    }

    @media (max-width: 768px) {
        .landing-h1 { font-size: 2.5rem; }
        .feature-grid { grid-template-columns: 1fr; }
        .audience-grid { grid-template-columns: repeat(2, 1fr); }
        .landing-nav { padding: 12px 20px; }
        .landing-nav-links { display: none; }
        .creator-section { flex-direction: column; text-align: center; }
    }
</style>
""", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Session State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
for key, default in {
    "leads_df": None,
    "run_count": 0,
    "total_leads": 0,
    "processing_time": 0.0,
    "search_history": [],
    "sheet_url": None,
    "pinned_searches": [],
    "active_search": None,
    "enriched_df": None,
    "pipeline": {},
    "pipeline_notes": {},
    "monitors": [],
    "show_app": False,
    "landing_section": "home",
    "active_tab": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Landing Page
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if not st.session_state.show_app:
    st.markdown(
        '<!-- NAV -->'
        '<div class="landing-nav">'
        '<div class="landing-nav-logo">⚡ LeadForge<span class="dot">.AI</span></div>'
        '<div class="landing-nav-links">'
        '<a href="#features">Product</a>'
        '<a href="#features">Features</a>'
        '<a href="#audience">Solutions</a>'
        '<a href="#creator">About</a>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── Hero ──
    st.markdown(
        '<div class="landing-hero">'
        '<div class="landing-badge">⚡ The Complete AI Lead Discovery Platform</div>'
        '<div class="landing-h1">Turn More Leads Into<br><span class="highlight">Customers</span></div>'
        '<div class="landing-sub">'
        'AI-powered lead discovery from Quora &amp; Pinterest. '
        'Discover, score, enrich, and manage leads — all from one platform. '
        'Built for startups, agencies, and growth teams.'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # CTA buttons
    col_a, col_b, col_c = st.columns([2, 1, 2])
    with col_b:
        if st.button("⚡ Launch App", use_container_width=True, type="primary"):
            st.session_state.show_app = True
            st.rerun()

    st.markdown("---")

    # ── Features Section ──
    st.markdown(
        '<div id="features" class="landing-section">'
        '<div class="landing-section-title">Powerful Features</div>'
        '<div class="landing-section-sub">Everything you need to discover, qualify, and convert leads — powered by AI.</div>'
        '<div class="feature-grid">'

        '<div class="feature-card">'
        '<div class="feature-icon">🔍</div>'
        '<h3>AI-Powered Search</h3>'
        '<p>Describe your ideal customer in plain English. Our AI transforms it into optimized queries and searches Quora &amp; Pinterest for matching leads.</p>'
        '</div>'

        '<div class="feature-card">'
        '<div class="feature-icon">🧠</div>'
        '<h3>Lead Enrichment</h3>'
        '<p>One-click AI enrichment estimates company, industry, and lead quality. Get personalized outreach drafts generated by Gemini for every lead.</p>'
        '</div>'

        '<div class="feature-card">'
        '<div class="feature-icon">🎯</div>'
        '<h3>Kanban Pipeline</h3>'
        '<p>Manage leads through Cold → Warm → Hot → Contacted → Converted stages. Add notes, move cards, and track your sales pipeline visually.</p>'
        '</div>'

        '<div class="feature-card">'
        '<div class="feature-icon">📡</div>'
        '<h3>Saved Monitors</h3>'
        '<p>Save your best-performing searches as monitors. Re-run them instantly to discover fresh leads on the same topics over time.</p>'
        '</div>'

        '<div class="feature-card">'
        '<div class="feature-icon">📊</div>'
        '<h3>Smart Scoring</h3>'
        '<p>Every lead is automatically scored 0–100 based on bio completeness, engagement signals, profile data, and source quality.</p>'
        '</div>'

        '<div class="feature-card">'
        '<div class="feature-icon">📤</div>'
        '<h3>Multi-Export</h3>'
        '<p>Export to Google Sheets with one click via Composio, or download as CSV/JSON. Upload your own CSVs for instant AI scoring.</p>'
        '</div>'

        '</div></div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ── Who Is It For ──
    st.markdown(
        '<div id="audience" class="landing-section">'
        '<div class="landing-section-title">Built For Growth Teams</div>'
        '<div class="landing-section-sub">Whether you\'re a solo founder or a sales team, LeadForge AI finds your next customers.</div>'
        '<div class="audience-grid">'

        '<div class="audience-card">'
        '<div class="audience-icon">🚀</div>'
        '<h4>Startup Founders</h4>'
        '<p>Find early adopters discussing your problem space on Q&amp;A platforms.</p>'
        '</div>'

        '<div class="audience-card">'
        '<div class="audience-icon">📈</div>'
        '<h4>Growth Marketers</h4>'
        '<p>Discover high-intent users and craft personalized outreach at scale.</p>'
        '</div>'

        '<div class="audience-card">'
        '<div class="audience-icon">🏢</div>'
        '<h4>Sales Teams</h4>'
        '<p>Build qualified pipelines from social signals instead of cold lists.</p>'
        '</div>'

        '<div class="audience-card">'
        '<div class="audience-icon">🎨</div>'
        '<h4>Agencies</h4>'
        '<p>Source leads for clients across industries with AI-powered discovery.</p>'
        '</div>'

        '</div></div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ── Creator Section ──
    st.markdown(
        '<div id="creator" class="landing-section">'
        '<div class="landing-section-title">Meet the Creator</div>'
        '<div class="landing-section-sub"></div>'
        '<div class="creator-section">'
        '<div class="creator-avatar">SG</div>'
        '<div class="creator-info">'
        '<h3>Sujay Gopal</h3>'
        '<div class="role">Builder &amp; Developer</div>'
        '<p>LeadForge AI was built to solve the #1 problem for startups: finding qualified leads without expensive tools. '
        'It combines Firecrawl for web intelligence, Google Gemini for AI analysis, and Composio for seamless exports — '
        'creating an end-to-end lead discovery engine that anyone can use.</p>'
        '</div>'
        '</div></div>',
        unsafe_allow_html=True
    )

    # ── Footer ──
    st.markdown(
        '<div class="landing-footer">'
        'LeadForge AI · Built with Streamlit · Firecrawl · Gemini · Composio<br>'
        '© 2026 Sujay Gopal. All rights reserved.'
        '</div>',
        unsafe_allow_html=True
    )

    st.stop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Load API keys
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_keys = get_api_keys()
google_key = _keys["google"]
firecrawl_key = _keys["firecrawl"]
composio_key = _keys["composio"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sidebar — Copilot Style
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    # Logo
    st.markdown(
        '<div class="logo-mark">'
        '<div class="logo-icon">⚡</div>'
        '<div><div class="logo-text">LeadForge AI</div>'
        '<div class="logo-sub">AI Lead Discovery</div></div>'
        '</div>', unsafe_allow_html=True
    )

    # Source selector
    st.markdown("### Sources")
    selected_sources = st.multiselect(
        "Search platforms",
        options=list(AVAILABLE_SOURCES.keys()),
        default=["quora"],
        format_func=lambda x: f"{AVAILABLE_SOURCES[x]['icon']} {AVAILABLE_SOURCES[x]['label']}",
        label_visibility="collapsed",
    )

    # Controls
    st.markdown("### Controls")
    num_links = st.slider(
        "Pages per source", min_value=1, max_value=10, value=DEFAULT_NUM_LINKS,
        help="More pages = more leads but slower",
    )

    enable_research = st.toggle("🌐 Web Research Mode", value=True,
        help="Pre-research the topic via Google & Wikipedia for better results")

    st.markdown("---")

    # Pinned Searches
    if st.session_state.pinned_searches:
        st.markdown('<div class="section-label">PINNED</div>', unsafe_allow_html=True)
        for ps in st.session_state.pinned_searches:
            st.markdown(
                f'<div class="lead-list-item pinned">'
                f'<div class="lead-item-title">• {ps["query"][:40]}</div>'
                f'<div class="lead-item-meta">{ps["leads"]} leads</div>'
                f'</div>', unsafe_allow_html=True
            )

    # Recent Searches
    if st.session_state.search_history:
        st.markdown('<div class="section-label">RECENT</div>', unsafe_allow_html=True)
        for item in reversed(st.session_state.search_history[-6:]):
            sources_str = ", ".join(item.get("sources", ["quora"]))
            st.markdown(
                f'<div class="lead-list-item">'
                f'<div class="lead-item-title">{item["query"][:42]}'
                f'<span class="lead-item-count">{item["leads"]} leads</span></div>'
                f'<div class="lead-item-meta">{sources_str} · {item["time"]}</div>'
                f'</div>', unsafe_allow_html=True
            )

        # Clear button
        if st.button("Clear history", key="clear_history"):
            st.session_state.search_history = []
            st.session_state.pinned_searches = []
            st.session_state.leads_df = None
            st.session_state.sheet_url = None
            st.session_state.run_count = 0
            st.session_state.total_leads = 0
            st.session_state.processing_time = 0.0

    st.markdown("---")

    # Connected Services
    st.markdown("### Services")
    g_color = "#c6ff00" if google_key else "#ff5252"
    f_color = "#c6ff00" if firecrawl_key else "#ff5252"
    c_color = "#c6ff00" if composio_key else "#666"

    st.markdown(
        f'<div class="api-card">'
        f'<div class="api-name">🧠 Gemini</div>'
        f'<div class="api-desc">Query transform · {DEFAULT_MODEL}</div>'
        f'<div class="api-status" style="color:{g_color};">{"● Connected" if google_key else "○ Missing"}</div>'
        f'</div>'
        f'<div class="api-card">'
        f'<div class="api-name">🔥 Firecrawl</div>'
        f'<div class="api-desc">Web search + AI extraction</div>'
        f'<div class="api-status" style="color:{f_color};">{"● Connected" if firecrawl_key else "○ Missing"}</div>'
        f'</div>'
        f'<div class="api-card">'
        f'<div class="api-name">📊 Composio</div>'
        f'<div class="api-desc">Google Sheets export</div>'
        f'<div class="api-status" style="color:{c_color};">{"● Connected" if composio_key else "○ Optional"}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # Rate limit info
    remaining = search_limiter.remaining()
    st.markdown(
        f'<div style="text-align:center;color:#333;font-size:0.6rem;padding:12px 0;">'
        f'{remaining}/10 searches remaining this minute'
        f'</div>', unsafe_allow_html=True
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main Content Area
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Header + Top-right navigation
col_title, col_nav = st.columns([2, 3])
with col_title:
    st.markdown(
        '<div style="padding:8px 0 16px;">'
        '<div class="main-title">⚡ LeadForge AI</div>'
        '<div style="font-size:0.75rem;color:#555;">AI-powered lead discovery from Quora & Pinterest</div>'
        '</div>', unsafe_allow_html=True
    )
with col_nav:
    nav_cols = st.columns(5)
    nav_items = [
        ("🔍 AI Search", "search"),
        ("📤 Bulk Upload", "bulk"),
        ("🎯 Pipeline", "pipeline"),
        ("📡 Monitors", "monitors"),
        ("📊 Results", "results"),
    ]
    for i, (label, key) in enumerate(nav_items):
        with nav_cols[i]:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.active_tab = key
                st.rerun()

active_tab = st.session_state.active_tab

# Metrics row
st.markdown(
    '<div class="metric-row">'
    f'<div class="metric-card"><div class="metric-value">{st.session_state.run_count}</div><div class="metric-label">Searches</div></div>'
    f'<div class="metric-card"><div class="metric-value">{st.session_state.total_leads}</div><div class="metric-label">Leads Found</div></div>'
    f'<div class="metric-card"><div class="metric-value">{st.session_state.processing_time:.1f}s</div><div class="metric-label">Last Run</div></div>'
    f'<div class="metric-card"><div class="metric-value">{DEFAULT_MODEL.split("-")[0].upper()} {DEFAULT_MODEL.split("-")[1]}</div><div class="metric-label">AI Model</div></div>'
    '</div>', unsafe_allow_html=True
)

# Firecrawl credit check
if firecrawl_key:
    try:
        _credit_resp = requests.get(
            "https://api.firecrawl.dev/v1/account",
            headers={"Authorization": f"Bearer {firecrawl_key}"},
            timeout=5,
        )
        if _credit_resp.status_code == 200:
            _credit_data = _credit_resp.json()
            _remaining = _credit_data.get("remaining_credits", _credit_data.get("credits"))
            if _remaining is not None:
                _ccolor = "#c6ff00" if _remaining > 10 else "#ffab00" if _remaining > 0 else "#ff5252"
                st.markdown(
                    f'<div style="text-align:right;font-size:0.72rem;color:{_ccolor};margin:-4px 0 8px;">'
                    f'🔥 Firecrawl credits: {_remaining} remaining</div>',
                    unsafe_allow_html=True
                )
        elif _credit_resp.status_code == 402:
            st.markdown(
                '<div class="error-banner">🔥 Firecrawl credits exhausted — '
                '<a href="https://www.firecrawl.dev/app/api-keys" style="color:#c6ff00;">add credits</a></div>',
                unsafe_allow_html=True
            )
    except Exception:
        pass

st.markdown("---")

# ── Default: Welcome Dashboard ────────────────────────
if active_tab is None:
    st.markdown(
        '<div style="text-align:center;padding:80px 0;">'
        '<div style="font-size:3.5rem;margin-bottom:16px;">⚡</div>'
        '<div style="font-size:1.5rem;font-weight:800;color:#eee;margin-bottom:8px;">Welcome to LeadForge AI</div>'
        '<div style="font-size:0.9rem;color:#555;max-width:500px;margin:0 auto 32px;line-height:1.7;">'
        'Select a section from the navigation above to get started. '
        'Use <strong style="color:#c6ff00;">AI Search</strong> to discover leads, '
        '<strong style="color:#c6ff00;">Bulk Upload</strong> to score CSVs, or '
        '<strong style="color:#c6ff00;">Pipeline</strong> to manage your funnel.'
        '</div>'
        '</div>', unsafe_allow_html=True
    )


# ── Section: AI Search ────────────────────────
if active_tab == "search":
    # Re-run from history
    if st.session_state.search_history:
        history_labels = ["New search..."] + [
            f"{h['query'][:55]}" for h in reversed(st.session_state.search_history[-6:])
        ]
        picked = st.selectbox("Re-run a previous search:", history_labels, index=0, label_visibility="collapsed")
        prefill = picked if picked != history_labels[0] else ""
    else:
        prefill = ""

    col_input, col_go = st.columns([4, 1])
    with col_input:
        user_query = st.text_area(
            "query",
            value=prefill,
            placeholder="e.g., Pizza website templates and design inspiration\n\nDescribe leads, topics, or content you want to find across Quora and Pinterest.",
            height=100, label_visibility="collapsed",
        )
    with col_go:
        st.markdown("<br>", unsafe_allow_html=True)
        run_search = st.button("⚡ Generate", use_container_width=True, type="primary")

    # Source indicator
    if selected_sources:
        source_tags = ""
        for s in selected_sources:
            css_class = f"source-{s}"
            source_tags += f'<span class="source-tag {css_class}">{AVAILABLE_SOURCES[s]["icon"]} {AVAILABLE_SOURCES[s]["label"]}</span> '
        st.markdown(f'<div style="margin:-8px 0 12px;">Searching: {source_tags}</div>', unsafe_allow_html=True)

    if run_search:
        if not user_query.strip():
            st.markdown('<div class="error-banner">Describe the leads or content you want to find.</div>', unsafe_allow_html=True)
            st.stop()

        # Validate keys
        _, missing_keys = get_validated_keys()
        if missing_keys:
            st.markdown(f'<div class="error-banner">Missing API keys: {", ".join(missing_keys)}. Add them to .env or Streamlit secrets.</div>', unsafe_allow_html=True)
            st.stop()

        # Rate limit check
        if not search_limiter.check():
            wait_time = search_limiter.reset_in()
            st.markdown(f'<div class="warning-banner">Rate limit reached. Try again in {wait_time:.0f} seconds.</div>', unsafe_allow_html=True)
            st.stop()

        if not selected_sources:
            st.markdown('<div class="error-banner">Select at least one source in the sidebar.</div>', unsafe_allow_html=True)
            st.stop()

        start_time = time.time()

        try:
            # Step 1 — Transform query
            with st.status("🧠 Optimizing your search query...", expanded=True) as s:
                client = create_prompt_transform_agent(google_key)
                company_description = transform_query(client, user_query)
                st.write(f'Query → **"{company_description}"**')
                s.update(label=f'✅ Query → "{company_description}"', state="complete")

            # Step 1.5 — Web Research
            research_context = ""
            if enable_research:
                with st.status("🌐 Researching topic...", expanded=True) as s:
                    research = research_topic(company_description, google_key)
                    google_count = len(research.get("google_results", []))
                    wiki_count = len(research.get("wiki_results", []))

                    if research.get("google_results"):
                        for r in research["google_results"][:3]:
                            title = r.get("title", "")
                            link = r.get("link", "")
                            if title and link:
                                st.write(f"- [{title}]({link})")
                            elif title:
                                st.write(f"- {title}")

                    research_context = research.get("summary_context", "")
                    s.update(label=f"✅ Research: {google_count} web + {wiki_count} wiki results", state="complete")

            # Step 2 — Search sources
            with st.status(f"🔍 Searching {', '.join(selected_sources)} for {num_links} pages each...", expanded=True) as s:
                url_items = search_for_urls(
                    company_description, firecrawl_key, num_links,
                    sources=selected_sources,
                )
                if not url_items:
                    st.warning("No URLs found. Try rephrasing your query or adding more sources.")
                    st.stop()

                for i, item in enumerate(url_items, 1):
                    source_label = item.get("source", "quora").capitalize()
                    st.write(f"{i}. [{source_label}] {item['url']}")
                s.update(label=f"✅ Found {len(url_items)} pages across {len(selected_sources)} sources", state="complete")

            # Step 3 — Extract leads
            with st.status("🧠 Extracting lead data...", expanded=True) as s:
                user_info_list = extract_user_info_from_urls(url_items, firecrawl_key)
                leads = format_leads_to_flat_json(user_info_list)
                if not leads:
                    st.warning("No leads extracted. Try a different query.")
                    st.stop()
                s.update(label=f"✅ Extracted {len(leads)} leads", state="complete")

            # Score leads
            df = pd.DataFrame(leads)
            df["Lead Score"] = df.apply(
                lambda r: min(100, max(10,
                    (30 if r.get("Bio", "") else 0)
                    + (25 if r.get("Profile URL", "") else 0)
                    + min(35, int(r.get("Upvotes", 0)) * 5)
                    + 10
                )), axis=1
            )
            df = df.sort_values("Lead Score", ascending=False).reset_index(drop=True)

            elapsed = time.time() - start_time

            # Update session state
            st.session_state.leads_df = df
            st.session_state.run_count += 1
            st.session_state.total_leads += len(df)
            st.session_state.processing_time = elapsed
            st.session_state.search_history.append({
                "query": user_query,
                "search_term": company_description,
                "leads": len(df),
                "sources": selected_sources,
                "time": datetime.now().strftime("%b %d, %I:%M %p"),
            })

            # Step 4 — Sheets export
            if composio_key:
                with st.status("📤 Exporting to Google Sheets...", expanded=True) as s:
                    sheet_url = write_to_google_sheets(leads, composio_key)
                    if sheet_url.startswith("Error"):
                        s.update(label=f"⚠️ {sheet_url[:80]}", state="error")
                    else:
                        st.session_state.sheet_url = sheet_url
                        s.update(label="✅ Exported to Google Sheets", state="complete")

            # Results
            st.success(f"Found {len(df)} leads in {elapsed:.1f}s")

            # Results header
            st.markdown(
                f'<div class="results-header">'
                f'<span class="results-title">• {user_query[:50]}</span>'
                f'<span class="results-badge">{len(df)} leads</span>'
                f'</div>', unsafe_allow_html=True
            )

            st.dataframe(df, use_container_width=True, hide_index=True, height=350)

            # Downloads
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "📥 CSV", df.to_csv(index=False),
                    f"leadforge_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv", use_container_width=True,
                )
            with col_dl2:
                st.download_button(
                    "📥 JSON", df.to_json(orient="records", indent=2),
                    f"leadforge_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    "application/json", use_container_width=True,
                )

            if st.session_state.sheet_url and not st.session_state.sheet_url.startswith("Error"):
                st.markdown(f"📊 **[Open Google Sheet]({st.session_state.sheet_url})**")

            # ── AI Enrichment ──
            st.markdown("---")
            col_enrich, col_pipeline = st.columns(2)
            with col_enrich:
                if st.button("🧠 AI Enrich Leads", use_container_width=True, type="primary", help="Add company estimates & outreach drafts via Gemini"):
                    with st.status("🧠 Enriching leads with AI...", expanded=True) as s:
                        progress_bar = st.progress(0)
                        def update_progress(current, total):
                            progress_bar.progress(current / total)
                            s.update(label=f"🧠 Enriching lead {current}/{total}...")
                        enriched = enrich_leads_batch(df, google_key, progress_callback=update_progress)
                        st.session_state.enriched_df = enriched
                        st.session_state.leads_df = enriched
                        s.update(label=f"✅ Enriched {len(enriched)} leads", state="complete")
                    st.rerun()
            with col_pipeline:
                if st.button("🎯 Send to Pipeline", use_container_width=True, type="primary", help="Add leads to the Kanban pipeline"):
                    for _, row in df.iterrows():
                        lead_id = f"{row.get('Username', 'unknown')}_{row.get('Source', 'unknown')}"
                        if lead_id not in st.session_state.pipeline:
                            score = int(row.get("Lead Score", 0))
                            if score >= 70:
                                stage = "Hot"
                            elif score >= 40:
                                stage = "Warm"
                            else:
                                stage = "Cold"
                            st.session_state.pipeline[lead_id] = {
                                "stage": stage,
                                "data": row.to_dict(),
                            }
                    st.success(f"Added {len(df)} leads to pipeline")

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 402:
                st.markdown(
                    '<div class="error-banner">'
                    '💳 Firecrawl credits exhausted (402 Payment Required). '
                    '<a href="https://www.firecrawl.dev/app/api-keys" style="color:#c6ff00;">Add credits here</a> '
                    'or reduce pages per search.'
                    '</div>', unsafe_allow_html=True
                )
            else:
                st.markdown(f'<div class="error-banner">HTTP Error: {e}</div>', unsafe_allow_html=True)
        except Exception as e:
            error_msg = str(e)
            # Never expose API keys in error messages
            for key_val in [google_key, firecrawl_key, composio_key]:
                if key_val and key_val in error_msg:
                    error_msg = error_msg.replace(key_val, "***")
            st.markdown(f'<div class="error-banner">Something went wrong: {error_msg}</div>', unsafe_allow_html=True)


# ── Section: Bulk Upload ────────────────────────
if active_tab == "bulk":
    st.markdown("### Upload CSV for Instant Scoring")
    st.markdown(
        '<div style="color:#666;font-size:0.85rem;margin-bottom:1rem;">'
        'Upload any CSV with lead data. Auto-detects columns and scores every row.'
        '</div>', unsafe_allow_html=True
    )

    uploaded = st.file_uploader("Drop your CSV here", type=["csv"], label_visibility="collapsed")

    if uploaded:
        # Security: limit file size (10MB)
        if uploaded.size > 10 * 1024 * 1024:
            st.markdown('<div class="error-banner">File too large. Max 10MB.</div>', unsafe_allow_html=True)
            st.stop()

        start = time.time()
        try:
            df_raw = pd.read_csv(uploaded)
        except Exception as e:
            st.markdown(f'<div class="error-banner">Invalid CSV: {e}</div>', unsafe_allow_html=True)
            st.stop()

        # Security: limit row count
        if len(df_raw) > 50000:
            st.markdown('<div class="warning-banner">CSV truncated to 50,000 rows.</div>', unsafe_allow_html=True)
            df_raw = df_raw.head(50000)

        row_count = len(df_raw)

        # Auto-detect columns
        col_map = {}
        for col in df_raw.columns:
            cl = col.lower().strip()
            if "user" in cl or "name" in cl: col_map[col] = "Username"
            elif "bio" in cl or "desc" in cl or "about" in cl: col_map[col] = "Bio"
            elif "url" in cl or "link" in cl or "website" in cl: col_map[col] = "Website URL"
            elif "upvote" in cl or "vote" in cl or "score" in cl: col_map[col] = "Upvotes"
            elif "type" in cl or "post" in cl: col_map[col] = "Post Type"
            elif "time" in cl or "date" in cl: col_map[col] = "Timestamp"
            elif "profile" in cl: col_map[col] = "Profile URL"
            elif "email" in cl: col_map[col] = "Email"
            elif "company" in cl or "org" in cl: col_map[col] = "Company"
            elif "title" in cl or "role" in cl or "position" in cl: col_map[col] = "Title"
        if col_map:
            df_raw = df_raw.rename(columns=col_map)

        # Score
        scores = pd.Series(10, index=df_raw.index)
        if "Bio" in df_raw.columns:
            scores += df_raw["Bio"].fillna("").apply(lambda x: 30 if len(str(x)) > 5 else 0)
        if "Profile URL" in df_raw.columns:
            scores += df_raw["Profile URL"].fillna("").apply(lambda x: 25 if len(str(x)) > 5 else 0)
        if "Upvotes" in df_raw.columns:
            scores += pd.to_numeric(df_raw["Upvotes"], errors="coerce").fillna(0).clip(0, 7) * 5
        if "Email" in df_raw.columns:
            scores += df_raw["Email"].fillna("").apply(lambda x: 15 if "@" in str(x) else 0)
        if "Company" in df_raw.columns:
            scores += df_raw["Company"].fillna("").apply(lambda x: 10 if len(str(x)) > 1 else 0)
        df_raw["Lead Score"] = scores.clip(0, 100).astype(int)
        df_scored = df_raw.sort_values("Lead Score", ascending=False).reset_index(drop=True)

        elapsed = time.time() - start
        st.session_state.leads_df = df_scored
        st.session_state.total_leads += row_count
        st.session_state.processing_time = elapsed
        st.session_state.run_count += 1

        rps = row_count / elapsed if elapsed > 0 else row_count
        st.markdown(
            f'<div style="margin:1rem 0;">'
            f'<span class="speed-stat">⚡ {row_count:,} rows</span>'
            f'<span class="speed-stat">🕐 {elapsed:.3f}s</span>'
            f'<span class="speed-stat">🚀 {rps:,.0f} rows/sec</span>'
            f'</div>', unsafe_allow_html=True
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 Hot (70+)", len(df_scored[df_scored["Lead Score"] >= 70]))
        c2.metric("🌤 Warm (40-69)", len(df_scored[(df_scored["Lead Score"] >= 40) & (df_scored["Lead Score"] < 70)]))
        c3.metric("❄️ Cold (<40)", len(df_scored[df_scored["Lead Score"] < 40]))

        st.dataframe(df_scored, use_container_width=True, hide_index=True, height=400)
        st.download_button("📥 Download Scored CSV", df_scored.to_csv(index=False), "leadforge_scored.csv", "text/csv")


# ── Section: Pipeline (Kanban) ────────────────────
if active_tab == "pipeline":
    st.markdown("### Lead Pipeline")

    if not st.session_state.pipeline:
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#333;">'
            '<div style="font-size:3rem;margin-bottom:12px;">🎯</div>'
            '<div style="font-size:1.1rem;color:#555;">Pipeline is empty</div>'
            '<div style="font-size:0.82rem;color:#333;">Run a search and click "Send to Pipeline" to populate</div>'
            '</div>', unsafe_allow_html=True
        )
    else:
        # Pipeline stats
        stage_counts = {}
        for stage in PIPELINE_STAGES:
            stage_counts[stage] = sum(1 for v in st.session_state.pipeline.values() if v["stage"] == stage)

        cols = st.columns(len(PIPELINE_STAGES))
        for i, stage in enumerate(PIPELINE_STAGES):
            color = PIPELINE_COLORS[stage]
            cols[i].markdown(
                f'<div style="text-align:center;padding:12px;background:#111;border:1px solid {color};'
                f'border-radius:10px;margin-bottom:8px;">'
                f'<div style="font-size:1.5rem;font-weight:800;color:{color};">{stage_counts[stage]}</div>'
                f'<div style="font-size:0.7rem;color:#888;text-transform:uppercase;">{stage}</div>'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("---")

        # Kanban columns
        kanban_cols = st.columns(len(PIPELINE_STAGES))
        for col_idx, stage in enumerate(PIPELINE_STAGES):
            with kanban_cols[col_idx]:
                color = PIPELINE_COLORS[stage]
                st.markdown(
                    f'<div style="font-size:0.75rem;font-weight:700;color:{color};'
                    f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;'
                    f'border-bottom:2px solid {color};padding-bottom:6px;">'
                    f'{stage} ({stage_counts[stage]})</div>', unsafe_allow_html=True
                )
                leads_in_stage = {k: v for k, v in st.session_state.pipeline.items() if v["stage"] == stage}
                for lead_id, lead_info in list(leads_in_stage.items())[:10]:
                    data = lead_info["data"]
                    username = str(data.get("Username", "Unknown"))[:20]
                    score = data.get("Lead Score", "?")
                    source = str(data.get("Source", ""))[:8]
                    note = st.session_state.pipeline_notes.get(lead_id, "")

                    st.markdown(
                        f'<div style="background:#111;border:1px solid #1a1a1a;border-radius:8px;'
                        f'padding:10px;margin-bottom:6px;font-size:0.75rem;">'
                        f'<div style="font-weight:600;color:#ddd;">{username}</div>'
                        f'<div style="color:#666;font-size:0.65rem;">{source} · Score: {score}</div>'
                        f'{"<div style=color:#c6ff00;font-size:0.62rem;margin-top:3px;>📝 " + note[:40] + "</div>" if note else ""}'
                        f'</div>', unsafe_allow_html=True
                    )

                    # Move buttons
                    stage_idx = PIPELINE_STAGES.index(stage)
                    bcol1, bcol2 = st.columns(2)
                    if stage_idx > 0:
                        if bcol1.button("◀", key=f"mv_left_{lead_id}", help=f"Move to {PIPELINE_STAGES[stage_idx-1]}"):
                            st.session_state.pipeline[lead_id]["stage"] = PIPELINE_STAGES[stage_idx - 1]
                            st.rerun()
                    if stage_idx < len(PIPELINE_STAGES) - 1:
                        if bcol2.button("▶", key=f"mv_right_{lead_id}", help=f"Move to {PIPELINE_STAGES[stage_idx+1]}"):
                            st.session_state.pipeline[lead_id]["stage"] = PIPELINE_STAGES[stage_idx + 1]
                            st.rerun()

        # Notes section
        st.markdown("---")
        st.markdown("#### Add Note to Lead")
        pipeline_leads = list(st.session_state.pipeline.keys())
        if pipeline_leads:
            selected_lead = st.selectbox("Select lead", pipeline_leads, format_func=lambda x: x.split("_")[0], label_visibility="collapsed")
            note_text = st.text_input("Note", value=st.session_state.pipeline_notes.get(selected_lead, ""), label_visibility="collapsed", placeholder="Add a note about this lead...")
            if st.button("💾 Save Note", type="primary"):
                st.session_state.pipeline_notes[selected_lead] = note_text
                st.success("Note saved")
                st.rerun()


# ── Section: Monitors ────────────────────────────
if active_tab == "monitors":
    st.markdown("### Saved Search Monitors")
    st.markdown(
        '<div style="color:#666;font-size:0.85rem;margin-bottom:1rem;">'
        'Save your searches to quickly re-run them. Monitors track your lead discovery patterns.'
        '</div>', unsafe_allow_html=True
    )

    # Save current search as monitor
    if st.session_state.search_history:
        st.markdown("#### Save a Search as Monitor")
        monitor_options = [f"{h['query'][:60]}" for h in st.session_state.search_history[-10:]]
        selected_monitor = st.selectbox("Pick a recent search to save:", monitor_options, label_visibility="collapsed")
        monitor_name = st.text_input("Monitor name", value=selected_monitor[:40] if selected_monitor else "", label_visibility="collapsed", placeholder="Name this monitor...")

        if st.button("📡 Save as Monitor", use_container_width=True, type="primary"):
            # Find the matching search history entry
            matching = [h for h in st.session_state.search_history if h["query"][:60] == selected_monitor]
            if matching:
                monitor = {
                    "name": monitor_name or selected_monitor[:40],
                    "query": matching[-1]["query"],
                    "sources": matching[-1].get("sources", ["quora"]),
                    "created": datetime.now().strftime("%b %d, %I:%M %p"),
                    "last_run": matching[-1].get("time", "Never"),
                    "total_leads": matching[-1].get("leads", 0),
                    "runs": 1,
                }
                st.session_state.monitors.append(monitor)
                st.success(f"Monitor '{monitor_name}' saved!")
                st.rerun()

    st.markdown("---")

    # Display saved monitors
    if st.session_state.monitors:
        st.markdown("#### Active Monitors")
        for i, monitor in enumerate(st.session_state.monitors):
            sources_str = ", ".join(monitor.get("sources", ["quora"]))
            st.markdown(
                f'<div style="background:#111;border:1px solid #1a1a1a;border-radius:10px;'
                f'padding:14px;margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div>'
                f'<div style="font-size:0.9rem;font-weight:700;color:#eee;">📡 {monitor["name"]}</div>'
                f'<div style="font-size:0.72rem;color:#666;margin-top:3px;">'
                f'{sources_str} · {monitor["total_leads"]} leads · {monitor["runs"]} runs</div>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<div style="font-size:0.65rem;color:#555;">Created: {monitor["created"]}</div>'
                f'<div style="font-size:0.65rem;color:#c6ff00;">Last: {monitor["last_run"]}</div>'
                f'</div></div></div>', unsafe_allow_html=True
            )

            col_run, col_del = st.columns([3, 1])
            with col_run:
                if st.button(f"▶ Re-run", key=f"run_monitor_{i}", use_container_width=True, type="primary"):
                    st.session_state.active_search = monitor["query"]
                    monitor["runs"] += 1
                    monitor["last_run"] = datetime.now().strftime("%b %d, %I:%M %p")
                    st.info(f"Go to AI Search tab — query pre-filled with: {monitor['query'][:50]}")
            with col_del:
                if st.button("🗑", key=f"del_monitor_{i}"):
                    st.session_state.monitors.pop(i)
                    st.rerun()
    else:
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#333;">'
            '<div style="font-size:3rem;margin-bottom:12px;">📡</div>'
            '<div style="font-size:1.1rem;color:#555;">No monitors yet</div>'
            '<div style="font-size:0.82rem;color:#333;">Run a search first, then save it as a monitor here</div>'
            '</div>', unsafe_allow_html=True
        )


# ── Section: Results ────────────────────────────
if active_tab == "results":
    if st.session_state.leads_df is not None and not st.session_state.leads_df.empty:
        df = st.session_state.leads_df
        st.markdown("### Lead Intelligence Dashboard")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df))
        if "Lead Score" in df.columns:
            c2.metric("Avg Score", f"{df['Lead Score'].mean():.0f}")
            c3.metric("Top Score", df["Lead Score"].max())
        if "Upvotes" in df.columns:
            c4.metric("Total Upvotes", f"{int(pd.to_numeric(df['Upvotes'], errors='coerce').fillna(0).sum()):,}")

        st.markdown("---")

        col_chart, col_table = st.columns([1, 2])
        with col_chart:
            if "Lead Score" in df.columns:
                st.markdown("#### Score Distribution")
                bins = pd.cut(df["Lead Score"], bins=[0, 25, 50, 75, 100], labels=["0-25", "26-50", "51-75", "76-100"])
                st.bar_chart(bins.value_counts().sort_index(), color="#c6ff00")

            # Source breakdown
            if "Source" in df.columns:
                st.markdown("#### By Source")
                st.bar_chart(df["Source"].value_counts(), color="#76ff03")

        with col_table:
            st.markdown("#### Top Leads")
            show_cols = [c for c in ["Source", "Username", "Bio", "Lead Score", "Upvotes", "Post Type", "Profile URL"] if c in df.columns]
            st.dataframe(df.head(25)[show_cols] if show_cols else df.head(25), use_container_width=True, hide_index=True, height=450)

        st.markdown("---")

        if st.session_state.sheet_url and not st.session_state.sheet_url.startswith("Error"):
            st.markdown(f"📊 **[Open Google Sheet]({st.session_state.sheet_url})**")

        col_csv, col_json = st.columns(2)
        with col_csv:
            st.download_button("📥 CSV", df.to_csv(index=False),
                f"leadforge_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv", use_container_width=True)
        with col_json:
            st.download_button("📥 JSON", df.to_json(orient="records", indent=2),
                f"leadforge_{datetime.now().strftime('%Y%m%d_%H%M')}.json", "application/json", use_container_width=True)
    else:
        st.markdown(
            '<div style="text-align:center;padding:80px 0;color:#333;">'
            '<div style="font-size:3rem;margin-bottom:12px;">🌊</div>'
            '<div style="font-size:1.1rem;color:#555;">No leads yet</div>'
            '<div style="font-size:0.82rem;color:#333;">Run an AI search or upload a CSV to get started</div>'
            '</div>', unsafe_allow_html=True
        )


# Footer
st.markdown(
    '<div class="app-footer">'
    'LeadForge AI · Firecrawl · Gemini · Composio · Streamlit'
    '</div>', unsafe_allow_html=True
)
