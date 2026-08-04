# LeadForge AI

LeadForge AI is a Streamlit application for two related tasks:

- Discover live, clickable web resources for a natural-language query.
- Discover social discussion pages and extract potential B2B leads from them.

**Live deployment:** [leadforge-ai-w0l7.onrender.com](https://leadforge-ai-w0l7.onrender.com)

## What it does

Enter a query such as `AI research papers`, `data science professors at ASU and USC`, or `SaaS founders struggling with customer onboarding`.

The application turns it into a focused query with Gemini few-shot prompting, then runs the appropriate retrieval paths:

| Query need | Result path | Output |
| --- | --- | --- |
| General web research | Gemini Google Search grounding | Real HTTP(S) website URLs with titles and snippets |
| Academic papers | arXiv API | Abstract pages and direct downloadable PDF links |
| Quora/Pinterest discussions | DuckDuckGo with source-native fallback | Relevant discussion or platform-search URLs |
| Lead qualification | BeautifulSoup + Gemini extraction | Structured social lead records, scores, and outreach drafts |

Live Web and Quora are selected by default. A Quora or Pinterest search failure does **not** prevent live web results from appearing.

## Search and fallback behavior

Search providers can rate-limit automated traffic or present bot-protection pages. LeadForge records and displays each recovery step in the interface.

1. It searches the selected discussion source with `ddgs` (DuckDuckGo).
2. It falls back to DuckDuckGo's lightweight HTML endpoint.
3. It uses Gemini-grounded citations for source-specific links.
4. If external search engines are blocked, it opens the selected platform's own search page instead.

For research-paper queries, LeadForge additionally queries arXiv directly. This makes paper discovery independent of DuckDuckGo and provides a stable `Download PDF` link where an arXiv record is available.

## Architecture

```text
lead_gen_agent/
├── app.py              # Streamlit UI and pipeline orchestration
├── agents.py           # Gemini query transform, lead enrichment, Sheets export
├── prompt_examples.py  # Few-shot query-transform examples
├── tools.py            # Gemini-grounded web, Wikipedia, and arXiv retrieval
├── scraper.py          # DuckDuckGo/source search and page extraction
├── search_recovery.py  # Retry, provider, and source-native fallback pipeline
├── config.py           # Configuration, sources, and rate limiter
├── requirements.txt    # Python dependencies
└── .env.example        # Environment-variable template
```

## Tech stack

| Component | Technology |
| --- | --- |
| UI | Streamlit |
| LLM and grounded web search | Google Gemini (`google-genai`) |
| Academic papers | arXiv API |
| Discussion discovery | DuckDuckGo (`ddgs`) with source-native fallback |
| Page parsing | Requests + BeautifulSoup |
| Lead data / exports | Pandas + optional Composio Google Sheets export |
| Deployment | Docker + Render |

## Local setup

Prerequisites:

- Python 3.12+ (the production Docker image uses Python 3.12)
- A `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey)
- Optional: `COMPOSIO_API_KEY` for Google Sheets export

```bash
git clone https://github.com/Sujay1709/LeadForge-AI.git
cd LeadForge-AI

python3 -m venv .venv
source .venv/bin/activate
pip install -r lead_gen_agent/requirements.txt

cp lead_gen_agent/.env.example lead_gen_agent/.env
streamlit run lead_gen_agent/app.py
```

Set the following values in `lead_gen_agent/.env`:

```dotenv
GOOGLE_API_KEY=your_google_ai_studio_key
COMPOSIO_API_KEY=optional_composio_key
```

The local application runs at <http://localhost:8501>.

## How to use it

1. Open **AI Search**.
2. Keep **Live Web** selected to receive live website URLs.
3. Add **Quora** or **Pinterest** if you also want discussion-source discovery and social lead extraction.
4. Search for a topic. For example, `AI research papers` returns grounded sites plus arXiv papers with PDF links.
5. For lead queries, review the scored lead table and optionally enrich leads or export them as CSV, JSON, or a Google Sheet.

## Render deployment

The repository includes a Docker-based Render configuration in `render.yaml`. In the Render dashboard, set:

- `GOOGLE_API_KEY` (required)
- `COMPOSIO_API_KEY` (optional)

Render builds the Docker image, installs dependencies from `lead_gen_agent/requirements.txt`, and starts Streamlit on port `8501`. The health endpoint is `/_stcore/health`.

The deployed app is currently available at [leadforge-ai-w0l7.onrender.com](https://leadforge-ai-w0l7.onrender.com).

## Known limitations

- Search engines and social platforms can block automated traffic. The recovery pipeline reports that condition and falls back where possible, but it cannot guarantee that every provider exposes every page.
- Google-grounded web results require a valid Google API key and Google Search grounding availability for the configured Gemini account.
- Social-page extraction depends on the public content a platform returns; profile fields may be incomplete or unavailable.

## License

MIT
