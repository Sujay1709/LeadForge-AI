"""
LeadForge AI — SaaS-grade Lead Generation Platform
Run with: streamlit run app.py
"""

import time
import json
import streamlit as st
import pandas as pd
from datetime import datetime

from config import get_api_keys, DEFAULT_NUM_LINKS, DEFAULT_MODEL
from scraper import search_for_urls, extract_user_info_from_urls, format_leads_to_flat_json
from agents import create_prompt_transform_agent, transform_query, write_to_google_sheets
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
# Custom CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* ── Global ── */
    .stApp { background: #0a0a0a; font-family: 'Inter', sans-serif; }
    header[data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }
    * { -webkit-tap-highlight-color: transparent; }

    /* ── Hero ── */
    .hero-title {
        font-size: 3.2rem; font-weight: 900; line-height: 1.1;
        background: linear-gradient(135deg, #c6ff00 0%, #76ff03 40%, #00e676 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem; letter-spacing: -0.03em;
    }
    .hero-sub { font-size: 1.1rem; color: #888; font-weight: 400; margin-bottom: 1.5rem; max-width: 600px; }

    /* ── Metric cards ── */
    .metric-row { display: flex; gap: 14px; margin: 1.2rem 0; }
    .metric-card {
        flex: 1; background: linear-gradient(145deg, #1a1a1a, #111);
        border: 1px solid #222; border-radius: 14px; padding: 20px;
        text-align: center; transition: all 0.25s cubic-bezier(.4,0,.2,1);
        cursor: default; user-select: none;
    }
    .metric-card:hover { border-color: #c6ff00; transform: translateY(-3px); box-shadow: 0 10px 35px rgba(198,255,0,0.1); }
    .metric-card:active { transform: translateY(0px) scale(0.98); }
    .metric-value { font-size: 2rem; font-weight: 800; color: #c6ff00; }
    .metric-label { font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px; }

    .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .badge-live { background: rgba(198,255,0,0.15); color: #c6ff00; animation: livePulse 2s ease-in-out infinite; }
    @keyframes livePulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; }
    .stTabs [data-baseweb="tab"] {
        background: #151515; border: 1px solid #222; border-radius: 8px;
        color: #888; padding: 8px 20px;
        transition: all 0.2s cubic-bezier(.4,0,.2,1) !important;
    }
    .stTabs [data-baseweb="tab"]:hover { background: #1a1a1a; border-color: #444; color: #ccc; transform: translateY(-1px); }
    .stTabs [data-baseweb="tab"]:active { transform: translateY(1px) scale(0.97); }
    .stTabs [aria-selected="true"] { background: #1a1a1a !important; border-color: #c6ff00 !important; color: #c6ff00 !important; }

    /* ── Primary Button (Generate) — touch-sensitive ── */
    .stButton > button {
        background: linear-gradient(135deg, #c6ff00, #76ff03) !important;
        color: #000 !important; font-weight: 700 !important;
        border: none !important; border-radius: 12px !important;
        padding: 0.65rem 2rem !important; font-size: 1rem !important;
        transition: all 0.15s cubic-bezier(.4,0,.2,1) !important;
        box-shadow: 0 2px 8px rgba(198,255,0,0.15) !important;
        position: relative; overflow: hidden;
    }
    .stButton > button:hover {
        transform: translateY(-2px) scale(1.03) !important;
        box-shadow: 0 6px 25px rgba(198,255,0,0.35) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) scale(0.96) !important;
        box-shadow: 0 1px 4px rgba(198,255,0,0.2) !important;
        transition: all 0.06s !important;
    }
    .stButton > button:focus-visible {
        outline: 2px solid #c6ff00 !important;
        outline-offset: 3px !important;
    }
    /* Ripple effect */
    .stButton > button::after {
        content: ''; position: absolute; inset: 0;
        background: radial-gradient(circle at var(--x,50%) var(--y,50%), rgba(255,255,255,0.3) 0%, transparent 60%);
        opacity: 0; transition: opacity 0.4s;
    }
    .stButton > button:active::after { opacity: 1; transition: opacity 0s; }

    /* ── Download Button — touch-sensitive ── */
    .stDownloadButton > button {
        background: #111 !important; border: 1px solid #333 !important;
        color: #c6ff00 !important; border-radius: 10px !important;
        transition: all 0.15s cubic-bezier(.4,0,.2,1) !important;
        font-weight: 600 !important;
    }
    .stDownloadButton > button:hover {
        border-color: #c6ff00 !important; background: #151515 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(198,255,0,0.12) !important;
    }
    .stDownloadButton > button:active {
        transform: translateY(1px) scale(0.97) !important;
        box-shadow: none !important; transition: all 0.06s !important;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] { background: #0d0d0d; border-right: 1px solid #1a1a1a; }
    section[data-testid="stSidebar"] .stMarkdown h3 { color: #c6ff00 !important; }
    /* Sidebar clear button */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important; border: 1px solid #333 !important;
        color: #ff5252 !important; font-size: 0.75rem !important;
        padding: 0.3rem 0.8rem !important; box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: #ff5252 !important; background: rgba(255,82,82,0.08) !important;
        transform: scale(1.02) !important; box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:active {
        transform: scale(0.95) !important;
    }

    /* ── Inputs ── */
    .stTextInput input, .stTextArea textarea {
        background: #111 !important; border: 1px solid #222 !important;
        color: #eee !important; border-radius: 10px !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #c6ff00 !important;
        box-shadow: 0 0 0 2px rgba(198,255,0,0.1) !important;
    }
    .stSlider [data-baseweb="slider"] [role="slider"] { background: #c6ff00 !important; }

    /* ── Toggle ── */
    .stToggle label span { transition: all 0.2s !important; }

    /* ── Pills ── */
    .speed-stat {
        font-size: 0.85rem; color: #76ff03; font-weight: 600;
        padding: 6px 14px; background: rgba(118,255,3,0.08);
        border-radius: 8px; display: inline-block; margin: 4px;
    }
    .feature-pill {
        display: inline-block; padding: 6px 14px; border-radius: 20px;
        background: #151515; border: 1px solid #222; color: #999;
        font-size: 0.75rem; margin: 3px; font-weight: 500;
        transition: all 0.2s;
    }
    .feature-pill:hover { border-color: #444; color: #ccc; transform: translateY(-1px); }
    hr { border-color: #1a1a1a !important; }

    /* ── API status cards ── */
    .api-card {
        background: #111; border: 1px solid #1e1e1e; border-radius: 12px;
        padding: 14px; margin: 8px 0; transition: all 0.25s cubic-bezier(.4,0,.2,1);
    }
    .api-card:hover { border-color: #333; transform: translateX(3px); }
    .api-name { font-size: 0.85rem; font-weight: 700; color: #ddd; margin-bottom: 4px; }
    .api-desc { font-size: 0.72rem; color: #666; line-height: 1.4; }
    .api-status { font-size: 0.7rem; font-weight: 600; margin-top: 6px; }

    /* ── History card ── */
    .history-card {
        padding: 10px 12px; margin: 6px 0; background: #111;
        border: 1px solid #1e1e1e; border-radius: 10px;
        transition: all 0.2s cubic-bezier(.4,0,.2,1); cursor: default;
    }
    .history-card:hover { border-color: #c6ff00; background: #151515; transform: translateX(3px); }
    .history-card:active { transform: translateX(1px) scale(0.98); }

    /* ── File uploader ── */
    .stFileUploader > div { border-radius: 12px !important; }

    /* ── Selectbox ── */
    .stSelectbox > div > div { background: #111 !important; border-color: #222 !important; }
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
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Load API keys
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_keys = get_api_keys()
google_key = _keys["google"]
firecrawl_key = _keys["firecrawl"]
composio_key = _keys["composio"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Enhanced Sidebar
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    # Logo area
    st.markdown(
        '<div style="text-align:center;padding:10px 0 20px;">'
        '<span style="font-size:2rem;">⚡</span><br>'
        '<span style="font-size:1.3rem;font-weight:800;'
        'background:linear-gradient(135deg,#c6ff00,#00e676);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
        'LeadForge AI</span>'
        '</div>', unsafe_allow_html=True
    )

    st.markdown("### 🎛️ Search Controls")

    num_links = st.slider(
        "🔗 Quora pages to scan",
        min_value=1, max_value=10, value=DEFAULT_NUM_LINKS,
        help="More pages = more leads but slower. Each page costs ~2 Firecrawl credits.",
    )

    st.markdown(
        f'<div style="text-align:center;color:#555;font-size:0.72rem;margin:-8px 0 12px;">'
        f'Estimated credits: ~{num_links * 2} search + ~{num_links} extract'
        f'</div>', unsafe_allow_html=True
    )

    enable_research = st.toggle(
        "🌐 Web Research Mode",
        value=True,
        help="Searches Google & Wikipedia first to build context, then uses that to find better Quora leads.",
    )

    st.markdown("---")

    # API Status Cards
    st.markdown("### 🔌 Connected Services")

    # Gemini
    g_status = "🟢 Connected" if google_key else "🔴 Missing"
    g_color = "#c6ff00" if google_key else "#ff5252"
    st.markdown(
        f'<div class="api-card">'
        f'<div class="api-name">🧠 Google Gemini</div>'
        f'<div class="api-desc">AI model for query transformation. Converts your natural language '
        f'descriptions into optimized search queries. Uses <b>{DEFAULT_MODEL}</b> (free tier).</div>'
        f'<div class="api-status" style="color:{g_color};">{g_status}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # Firecrawl
    f_status = "🟢 Connected" if firecrawl_key else "🔴 Missing"
    f_color = "#c6ff00" if firecrawl_key else "#ff5252"
    st.markdown(
        f'<div class="api-card">'
        f'<div class="api-name">🔥 Firecrawl</div>'
        f'<div class="api-desc">Web search & AI extraction engine. Discovers Quora discussions '
        f'matching your query, then uses LLM to extract structured user data (usernames, bios, '
        f'upvotes, profile URLs) from each page.</div>'
        f'<div class="api-status" style="color:{f_color};">{f_status}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # Composio
    c_status = "🟢 Connected" if composio_key else "⚪ Optional"
    c_color = "#c6ff00" if composio_key else "#888"
    st.markdown(
        f'<div class="api-card">'
        f'<div class="api-name">📊 Composio</div>'
        f'<div class="api-desc">Google Sheets integration. Automatically creates a new spreadsheet '
        f'with your extracted leads. Requires one-time Google account connection via '
        f'<a href="https://app.composio.dev" style="color:#c6ff00;">Composio dashboard</a>.</div>'
        f'<div class="api-status" style="color:{c_color};">{c_status}</div>'
        f'</div>', unsafe_allow_html=True
    )

    st.markdown("---")

    # Search History
    hist_header, hist_clear = st.columns([3, 1])
    with hist_header:
        st.markdown("### 🕒 History")
    with hist_clear:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear", key="clear_history", use_container_width=True):
            st.session_state.search_history = []
            st.session_state.leads_df = None
            st.session_state.sheet_url = None
            st.session_state.run_count = 0
            st.session_state.total_leads = 0
            st.session_state.processing_time = 0.0
            st.rerun()

    if st.session_state.search_history:
        for item in reversed(st.session_state.search_history[-8:]):
            st.markdown(
                f'<div class="history-card">'
                f'<div style="font-size:0.8rem;color:#c6ff00;font-weight:600;">'
                f'✅ {item["leads"]} leads found</div>'
                f'<div style="font-size:0.75rem;color:#aaa;margin:3px 0;">'
                f'"{item["query"][:50]}"</div>'
                f'<div style="font-size:0.65rem;color:#444;">'
                f'🔍 {item["search_term"]} · {item["time"]}</div>'
                f'</div>', unsafe_allow_html=True
            )
    else:
        st.markdown(
            '<div style="text-align:center;padding:20px 0;color:#333;font-size:0.8rem;">'
            'No searches yet.'
            '</div>', unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;color:#333;font-size:0.65rem;padding:8px 0;">'
        'Keys loaded from .env · No data stored externally'
        '</div>', unsafe_allow_html=True
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Hero
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
col_hero, col_badge = st.columns([4, 1])
with col_hero:
    st.markdown('<div class="hero-title">LeadForge AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-sub">'
        'AI-powered lead discovery from Quora. Describe your ideal customer, '
        'get qualified leads with scores — exported to Google Sheets automatically.'
        '</div>', unsafe_allow_html=True
    )
with col_badge:
    st.markdown('<br><span class="badge badge-live">● Live</span>', unsafe_allow_html=True)

st.markdown(
    '<div>'
    '<span class="feature-pill">🎯 Smart Search</span>'
    '<span class="feature-pill">🧠 AI Extraction</span>'
    '<span class="feature-pill">📊 Lead Scoring</span>'
    '<span class="feature-pill">⚡ Bulk Processing</span>'
    '<span class="feature-pill">📥 CSV / Sheets Export</span>'
    '</div>', unsafe_allow_html=True
)
st.markdown("---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Metrics
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(
    '<div class="metric-row">'
    f'<div class="metric-card"><div class="metric-value">{st.session_state.run_count}</div><div class="metric-label">Searches</div></div>'
    f'<div class="metric-card"><div class="metric-value">{st.session_state.total_leads}</div><div class="metric-label">Leads Found</div></div>'
    f'<div class="metric-card"><div class="metric-value">{st.session_state.processing_time:.1f}s</div><div class="metric-label">Last Run</div></div>'
    f'<div class="metric-card"><div class="metric-value">{DEFAULT_MODEL.split("-")[0].upper()} {DEFAULT_MODEL.split("-")[1]}</div><div class="metric-label">AI Model</div></div>'
    '</div>', unsafe_allow_html=True
)
st.markdown("---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tabs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
tab_search, tab_bulk, tab_results = st.tabs(["🔍 AI Search", "📤 Bulk Upload", "📊 Results"])


# ── Tab 1: AI Search ──────────────────────────
with tab_search:
    # Quick-select from history
    if st.session_state.search_history:
        history_labels = ["Type a new search..."] + [
            f"{h['query'][:55]}" for h in reversed(st.session_state.search_history[-8:])
        ]
        picked = st.selectbox("📋 Or re-run a previous search:", history_labels, index=0, label_visibility="collapsed")
        prefill = picked if picked != history_labels[0] else ""
    else:
        prefill = ""

    col_input, col_go = st.columns([4, 1])
    with col_input:
        user_query = st.text_area(
            "query",
            value=prefill,
            placeholder="e.g., SaaS founders looking for customer onboarding tools\n\nDescribe the type of leads you want to find. Be specific about industry, pain points, or tools they need.",
            height=110, label_visibility="collapsed",
        )
    with col_go:
        st.markdown("<br>", unsafe_allow_html=True)
        run_search = st.button("⚡ Generate", use_container_width=True)

    if run_search:
        if not user_query.strip():
            st.error("Describe the leads you want to find.")
            st.stop()
        if not google_key or not firecrawl_key:
            missing = []
            if not google_key: missing.append("GOOGLE_API_KEY")
            if not firecrawl_key: missing.append("FIRECRAWL_API_KEY")
            st.error(f"Missing in .env: {', '.join(missing)}")
            st.stop()

        start_time = time.time()

        try:
            # Step 1 — Transform query
            with st.status("🧠 AI is optimizing your search query...", expanded=True) as s:
                client = create_prompt_transform_agent(google_key)
                company_description = transform_query(client, user_query)
                st.write(f"**Optimized search:** `{company_description}`")
                s.update(label=f'✅ Query → "{company_description}"', state="complete")

            # Step 1.5 — Web Research (Google + Wikipedia)
            research_context = ""
            if enable_research:
                with st.status("🌐 Researching topic via Google & Wikipedia...", expanded=True) as s:
                    research = research_topic(company_description, google_key)

                    google_count = len(research.get("google_results", []))
                    wiki_count = len(research.get("wiki_results", []))

                    if research.get("google_results"):
                        st.write("**Google Results:**")
                        for r in research["google_results"][:3]:
                            title = r.get("title", "")
                            snippet = r.get("snippet", "")
                            link = r.get("link", "")
                            if title:
                                if link:
                                    st.write(f"- [{title}]({link})")
                                else:
                                    st.write(f"- {title}: {snippet[:100]}")

                    if research.get("wiki_results"):
                        st.write("**Wikipedia:**")
                        for r in research["wiki_results"]:
                            st.write(f"- **{r['title']}**: {r['summary'][:120]}...")

                    research_context = research.get("summary_context", "")
                    s.update(label=f"✅ Research: {google_count} web + {wiki_count} wiki results", state="complete")

            # Step 2 — Search Quora
            with st.status(f"🔍 Searching Quora for {num_links} relevant pages...", expanded=True) as s:
                urls = search_for_urls(company_description, firecrawl_key, num_links)
                if not urls:
                    st.warning("No Quora URLs found. Try rephrasing your query.")
                    st.stop()
                for i, u in enumerate(urls, 1):
                    st.write(f"{i}. {u}")
                s.update(label=f"✅ Found {len(urls)} Quora discussions", state="complete")

            # Step 3 — Extract leads
            with st.status("🧠 AI is extracting lead data from each page...", expanded=True) as s:
                user_info_list = extract_user_info_from_urls(urls, firecrawl_key)
                leads = format_leads_to_flat_json(user_info_list)
                if not leads:
                    st.warning("No leads extracted. The pages may have limited user data. Try a different query.")
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
                "researched": enable_research,
                "time": datetime.now().strftime("%b %d, %I:%M %p"),
            })

            # Step 4 — Export to Sheets (subprocess — won't crash main app)
            if composio_key:
                with st.status("📤 Exporting to Google Sheets...", expanded=True) as s:
                    sheet_url = write_to_google_sheets(leads, composio_key)
                    if sheet_url.startswith("Error"):
                        s.update(label=f"⚠️ Sheets: {sheet_url}", state="error")
                        st.warning(f"Sheets export issue: {sheet_url}. Leads are still available below.")
                    else:
                        st.session_state.sheet_url = sheet_url
                        s.update(label="✅ Exported to Google Sheets", state="complete")
                        st.markdown(f"📊 **[Open Google Sheet]({sheet_url})**")

            # Show results inline (no st.rerun — avoids crash)
            st.success(f"Done — {len(df)} leads scored in {elapsed:.1f}s")

            # Preview
            st.markdown("### Results Preview")
            st.dataframe(df, use_container_width=True, hide_index=True, height=350)

            # Downloads
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "📥 Download CSV",
                    df.to_csv(index=False),
                    f"leadforge_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv", use_container_width=True,
                )
            with col_dl2:
                st.download_button(
                    "📥 Download JSON",
                    df.to_json(orient="records", indent=2),
                    f"leadforge_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    "application/json", use_container_width=True,
                )

        except Exception as e:
            st.error(f"Something went wrong: {e}")


# ── Tab 2: Bulk Upload ────────────────────────
with tab_bulk:
    st.markdown("### Upload CSV for Instant Scoring")
    st.markdown(
        '<div style="color:#888;font-size:0.9rem;margin-bottom:1rem;">'
        'Upload any CSV with lead data. LeadForge auto-detects columns and scores every row.'
        '</div>', unsafe_allow_html=True
    )

    uploaded = st.file_uploader("Drop your CSV here", type=["csv"], label_visibility="collapsed")

    if uploaded:
        start = time.time()
        df_raw = pd.read_csv(uploaded)
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


# ── Tab 3: Results ────────────────────────────
with tab_results:
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
            if "Post Type" in df.columns:
                st.markdown("#### By Post Type")
                st.bar_chart(df["Post Type"].fillna("Unknown").value_counts(), color="#76ff03")

        with col_table:
            st.markdown("#### Top Leads")
            show_cols = [c for c in ["Username", "Bio", "Lead Score", "Upvotes", "Post Type", "Profile URL"] if c in df.columns]
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
            '<div style="text-align:center;padding:80px 0;color:#444;">'
            '<div style="font-size:3rem;margin-bottom:12px;">📊</div>'
            '<div style="font-size:1.1rem;">No leads yet</div>'
            '<div style="font-size:0.85rem;color:#333;">Run an AI search or upload a CSV to get started</div>'
            '</div>', unsafe_allow_html=True
        )


# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#333;font-size:0.7rem;padding:12px 0;">'
    'LeadForge AI · Firecrawl · Gemini · Composio · Streamlit'
    '</div>', unsafe_allow_html=True
)
