# CLAUDE.md — AI Lead Generation Agent

## Project Overview

This is an AI-powered lead generation system that discovers and qualifies potential B2B/SaaS leads from Quora, then exports them to Google Sheets. It combines Firecrawl (web search + LLM extraction), Phidata (agent orchestration), Composio (Google Sheets integration), and Streamlit (UI).

The primary entry point is `lead_gen_agent/app.py`, run via `streamlit run lead_gen_agent/app.py`.

## Architecture

```
lead_gen_agent/
├── app.py           # Streamlit UI — orchestrates the full pipeline
├── agents.py        # Phidata agent definitions (query transform + Sheets export)
├── scraper.py       # Firecrawl search + LLM extract logic
├── schemas.py       # Pydantic models for structured Quora data
├── config.py        # Env vars, defaults, constants
├── requirements.txt # Python dependencies
└── .env.example     # API key template
```

### Pipeline Flow

1. **Query Transform** (`agents.py → create_prompt_transform_agent`) — Takes a verbose natural-language lead description and distills it to a 3–6 word search phrase via GPT-4o-mini.
2. **URL Search** (`scraper.py → search_quora_urls`) — Hits `POST https://api.firecrawl.dev/v1/search` with the concise query, filters results to `quora.com` URLs only.
3. **Data Extraction** (`scraper.py → extract_users_from_urls`) — For each URL, calls `FirecrawlApp.extract()` with a Pydantic JSON schema (`QuoraPageSchema`) to pull structured user data.
4. **Flattening** (`scraper.py → flatten_leads`) — Converts nested extraction results into a flat list of dicts, one per user interaction.
5. **Sheets Export** (`agents.py → write_leads_to_sheets`) — A Phidata agent with Composio's `GOOGLESHEETS_SHEET_FROM_JSON` tool creates a new Google Sheet and populates it.

### Module Responsibilities

- **`config.py`** — Single source of truth for environment variables and defaults. All API keys are loaded from `.env` via `python-dotenv`. Constants: `DEFAULT_NUM_LINKS` (5), `DEFAULT_SEARCH_LOCATION` ("United States"), `DEFAULT_SEARCH_LANG` ("en"), `DEFAULT_MODEL` ("gpt-4o-mini").
- **`schemas.py`** — Three Pydantic v2 models: `QuoraUserInteraction` (individual post data), `QuoraPageSchema` (page-level container passed to Firecrawl extract), `FlattenedLead` (export-ready record). The `QuoraPageSchema.model_json_schema()` output is sent directly to Firecrawl's extract endpoint.
- **`scraper.py`** — Pure functions, no agent logic. `search_quora_urls` uses raw `requests.post` against Firecrawl's REST API. `extract_users_from_urls` uses the `FirecrawlApp` Python SDK. Both accept API keys as parameters (no global state).
- **`agents.py`** — Two agent factories plus one convenience function. Agents are stateless — created fresh per invocation. The Sheets agent uses `ComposioToolSet` to get the Google Sheets tool, which is passed to a Phidata `Agent`.
- **`app.py`** — Streamlit app with sidebar for API key input (pre-filled from `.env`), main area for query + link count, and a sequential pipeline with `st.status` progress indicators. Leads are previewed as a dataframe before export.

## Key Dependencies

| Package | Purpose | Import Pattern |
|---------|---------|---------------|
| `streamlit` | Web UI | `import streamlit as st` |
| `phidata` | Agent framework | `from phi.agent import Agent; from phi.model.openai import OpenAIChat` |
| `firecrawl-py` | Web scraping SDK | `from firecrawl import FirecrawlApp` |
| `composio-phidata` | Sheets integration | `from composio_phidata import Action, ComposioToolSet` |
| `pydantic` | Data schemas | `from pydantic import BaseModel, Field` |
| `python-dotenv` | Env loading | `from dotenv import load_dotenv` |
| `requests` | HTTP calls | `import requests` |

## External API Contracts

### Firecrawl Search (`scraper.py:search_quora_urls`)
- Endpoint: `POST https://api.firecrawl.dev/v1/search`
- Auth: `Authorization: Bearer {key}`
- Payload: `{ "query": str, "limit": int, "lang": str, "location": str }`
- Response: `{ "success": bool, "data": [{ "url": str, ... }] }`
- Cost: 2 credits per 10 search results (no scrape); scrape adds per-page cost

### Firecrawl Extract (`scraper.py:extract_users_from_urls`)
- Method: `FirecrawlApp.extract(urls: List[str], params: dict)`
- Params include `"prompt"` (extraction instructions) and `"schema"` (JSON Schema from Pydantic)
- Response: `{ "success": bool, "data": { "user_interactions": [...] } }`

### Composio Google Sheets (`agents.py:create_google_sheets_agent`)
- Action: `Action.GOOGLESHEETS_SHEET_FROM_JSON`
- Requires: `composio add googlesheets` CLI setup + active integration in Composio dashboard
- The agent receives JSON string of leads and instructs the tool to create a titled sheet

## Environment Variables

All defined in `.env` (see `.env.example`):

| Variable | Required | Source |
|----------|----------|--------|
| `OPENAI_API_KEY` | Yes | https://platform.openai.com/api-keys |
| `FIRECRAWL_API_KEY` | Yes | https://www.firecrawl.dev/app/api-keys |
| `COMPOSIO_API_KEY` | Yes | https://app.composio.dev/developers |

Keys can also be entered at runtime via the Streamlit sidebar. Sidebar values override `.env` values.

## Development Conventions

### Code Style
- Python 3.10+ required
- Type hints on all function signatures
- Google-style docstrings with Args/Returns sections
- Pydantic v2 models (use `model_json_schema()`, not v1's `schema()`)
- No global mutable state — API keys are passed as function parameters
- Imports are grouped: stdlib → third-party → local modules

### Error Handling
- `scraper.py` uses try/except per URL in extraction loops — one failed URL doesn't break the batch
- `app.py` wraps the entire pipeline in a top-level try/except, surfacing errors via `st.error`
- HTTP calls use `response.raise_for_status()` for clear failure on bad status codes
- Firecrawl responses are checked for `"success": true` before accessing data

### Adding New Lead Sources
To add a source beyond Quora:
1. Add a new schema in `schemas.py` for the source's data shape
2. Add search + extract functions in `scraper.py` (or create a new module, e.g., `reddit_scraper.py`)
3. Wire the new source into `app.py`'s pipeline, keeping the same pattern: search → extract → flatten → export

### Adding New Export Targets
To export to something other than Google Sheets:
1. Add a new Composio action or direct API integration in `agents.py`
2. Follow the same pattern: create an agent factory function + a convenience wrapper
3. Add a selector in `app.py` to choose export target

### Modifying the Extraction Schema
If you need additional fields from Quora (e.g., follower count, answer count):
1. Add the field to `QuoraUserInteraction` in `schemas.py`
2. Update the extraction prompt in `scraper.py → extract_users_from_urls` to mention the new field
3. Add the field to the flattened dict in `scraper.py → flatten_leads`
4. Update the column list in `agents.py → write_leads_to_sheets` message

## Running the App

```bash
# 1. Install dependencies
cd lead_gen_agent
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Connect Google Sheets (one-time)
composio add googlesheets

# 4. Launch
streamlit run app.py
```

The app will be available at http://localhost:8501.

## Common Issues

- **"No Quora URLs found"** — The Firecrawl search returned results but none were from quora.com. Try a broader or differently-worded query.
- **Extraction returns empty data** — Quora pages may block scraping or have changed structure. Check Firecrawl credit balance and try different URLs.
- **Composio auth errors** — Re-run `composio add googlesheets` and verify the connection is active in the Composio dashboard's active integrations tab.
- **Import errors** — Ensure you're running from the `lead_gen_agent/` directory so relative imports resolve correctly.

## Cost Awareness

- Firecrawl: ~2 credits per 10 search results + extraction credits per page
- OpenAI: GPT-4o-mini calls for query transform and Sheets agent (low cost per call)
- Composio: Free tier available; check plan limits for Google Sheets actions
