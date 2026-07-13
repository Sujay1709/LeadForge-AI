<p align="center">
  <h1 align="center">LeadForge AI</h1>
  <p align="center">AI-powered B2B lead generation from Quora — discover, qualify, and export leads in one click.</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Gemini-2.5--flash-4285F4?logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/Firecrawl-v4-orange" alt="Firecrawl">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## What It Does

LeadForge AI discovers potential B2B/SaaS leads by searching Quora for people actively asking about problems your product solves. It uses LLM-powered extraction to pull structured user data from Quora pages, then exports everything to Google Sheets.

**Pipeline:** Natural language query &rarr; Gemini query transform &rarr; Firecrawl Quora search &rarr; LLM extraction &rarr; Lead scoring &rarr; Google Sheets export

## Features

- **AI Query Transform** — Describe your ideal customer in plain English; Gemini 2.5 Flash distills it into an optimized search phrase using 10 few-shot examples across B2B verticals.
- **Quora Lead Discovery** — Firecrawl searches Quora for relevant discussions, then uses LLM extract to pull structured user data (username, bio, post type, upvotes, profile URL).
- **Research Mode** — Optional Google Search (via Gemini grounding) and Wikipedia enrichment to give the AI richer industry context before searching.
- **Lead Scoring** — Automatic quality scoring based on bio completeness, engagement signals, and profile data availability.
- **Bulk Upload** — Paste or upload a list of Quora URLs to extract leads from directly.
- **Google Sheets Export** — One-click export via Composio creates a formatted spreadsheet with all lead data.
- **CSV/JSON Download** — Export leads locally in either format.
- **Search History** — Sidebar tracks previous searches with timestamps for quick reference.
- **Dark Futuristic UI** — Premium dark theme with touch-sensitive animated buttons, smooth transitions, and a responsive layout.

## Architecture

```
lead_gen_agent/
├── app.py           # Streamlit UI — full pipeline orchestration
├── agents.py        # Gemini query transform + Composio Sheets export
├── scraper.py       # Firecrawl search + LLM extract + scrape fallback
├── schemas.py       # Pydantic v2 models for structured Quora data
├── tools.py         # Google Search (Gemini grounding) + Wikipedia lookup
├── config.py        # Environment variables and defaults
├── requirements.txt # Python dependencies
└── .env.example     # API key template
```

### Pipeline Flow

1. **Query Transform** — `agents.py` uses `google-genai` to call Gemini 2.5 Flash with a few-shot prompt, converting verbose lead descriptions into 3–6 word search phrases.
2. **Research (optional)** — `tools.py` runs Google Search via Gemini grounding and Wikipedia REST API to build industry context.
3. **URL Search** — `scraper.py` hits `POST https://api.firecrawl.dev/v1/search` with the concise query, filtering to `quora.com` URLs only.
4. **Data Extraction** — For each URL, `FirecrawlApp.extract()` (v4 SDK, keyword args) pulls structured data using a Pydantic JSON schema. Falls back to markdown scraping if extract returns empty.
5. **Deduplication & Flattening** — Nested results are flattened into one record per user, deduplicated by (username, URL).
6. **Sheets Export** — Composio runs in a subprocess (isolated for Python 3.14 stability) to create a Google Sheet via `GOOGLESHEETS_SHEET_FROM_JSON`.

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| UI | Streamlit 1.30+ | Web interface with dark theme |
| LLM | Google Gemini 2.5 Flash (`google-genai`) | Query transformation, grounded search |
| Web Scraping | Firecrawl v4 (`firecrawl-py`) | Quora search + LLM data extraction |
| Sheets Export | Composio (`composio`) | Google Sheets integration |
| Data Models | Pydantic v2 | Structured extraction schemas |
| Research | Wikipedia REST API | Free encyclopedia context |

## Setup

### Prerequisites

- Python 3.10+ (tested on 3.14)
- API keys for Google (Gemini), Firecrawl, and Composio

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/LeadForge-AI.git
cd LeadForge-AI/lead_gen_agent

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

### API Keys

| Variable | Get it from |
|----------|------------|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `FIRECRAWL_API_KEY` | [Firecrawl Dashboard](https://www.firecrawl.dev/app/api-keys) |
| `COMPOSIO_API_KEY` | [Composio Dashboard](https://app.composio.dev/developers) |

### Google Sheets Connection (one-time)

```bash
pip install composio-core
composio add googlesheets
```

### Run

```bash
cd lead_gen_agent
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Usage

1. Enter a natural language description of your ideal customer (e.g., "SaaS founders who need better customer onboarding tools").
2. Adjust the number of Quora links to search (1–20).
3. Toggle **Research Mode** for richer context via Google Search + Wikipedia.
4. Click **Generate Leads** and wait for the pipeline to complete.
5. Preview leads in the results table, then export to Google Sheets or download as CSV/JSON.

## Python 3.14 Compatibility

This project is specifically engineered for Python 3.14 compatibility:

- Uses `google-genai` (new SDK) instead of deprecated `google-generativeai` which segfaults on 3.14.
- Removed `phidata` dependency entirely (it imports the deprecated SDK internally).
- Composio runs in a subprocess to isolate potential segfaults from the main Streamlit process.
- Avoids `st.rerun()` which causes Streamlit crashes on 3.14.

## Cost

- **Firecrawl**: ~2 credits per 10 search results + extraction credits per page
- **Gemini**: 2.5 Flash is low-cost per call (query transform + optional grounded search)
- **Composio**: Free tier available for Google Sheets actions

## License

MIT
