# LeadForge AI — Shipping, Scaling & Monetization Playbook

## Phase 1: Ship It (Week 1-2)

### Deploy to Production (Free Options)

**Option A: Streamlit Community Cloud (100% Free)**
- Go to share.streamlit.io → connect your GitHub repo
- Select lead_gen_agent/app.py as the main file
- Add env vars (GOOGLE_API_KEY, FIRECRAWL_API_KEY, COMPOSIO_API_KEY)
- Gets you: yourapp.streamlit.app

**Option B: Railway (Free $5 credit/mo)**
- railway.com → New Project → Deploy from GitHub
- Auto-detects Dockerfile and railway.toml
- Add env vars in dashboard
- Gets you: leadforge-ai.up.railway.app
- Custom domain: add CNAME record at your registrar

**Option C: Render (Free tier available)**
- render.com → New → Blueprint → point to repo
- render.yaml auto-configures everything
- Free tier: 750 hours/month

### Get a Domain

Buy leadforgeai.com from Namecheap or Cloudflare (~$10-15/year).

## Phase 2: Get Users (Week 2-6)

### Free Distribution Channels

1. **Product Hunt** — Post on Tuesday. Title: "LeadForge AI — Find B2B leads from Quora with AI."
2. **Indie Hackers / Hacker News** — "Show HN" post about the Gemini + Firecrawl stack
3. **LinkedIn** — Problem-solution posts 3x/week
4. **Quora** — Answer lead gen questions, mention LeadForge
5. **Reddit** — r/SaaS, r/startups, r/Entrepreneur, r/marketing

## Phase 3: Monetize (Week 6+)

### Pricing: Hybrid (Subscription + Credits)

| Plan | Price | Credits/mo | Features |
|------|-------|-----------|----------|
| Free | $0 | 10 | CSV export only |
| Starter | $29/mo | 100 | + Sheets export, Research mode |
| Pro | $79/mo | 500 | + Priority support, API access |
| Scale | $199/mo | 2,000 | + Dedicated support, Custom sources |

The usage.py module has this plan structure built in.

### Revenue Math

| Scenario | Paid Users | MRR | ARR |
|----------|-----------|-----|-----|
| Conservative | 25 | $1,450 | $17,400 |
| Moderate | 150 | $8,700 | $104,400 |
| Growth | 800 | $46,400 | $556,800 |

## Phase 4: Scale (Month 3+)

### Add More Lead Sources
- Reddit, Twitter/X, LinkedIn, G2 Reviews, Stack Overflow
- Each source = new module following search → extract → flatten → export

### Add More Export Targets
- HubSpot CRM, Salesforce, Airtable, Slack/Email alerts, Webhook/API

### Build an API
- FastAPI wrapper around core pipeline
- Charge per-call or per-lead

## Phase 5: Defensibility

1. Data flywheel — more users = better query templates
2. Source breadth — each platform integration is a moat
3. Scoring models — train on conversion data
4. Workflow integration — deep CRM integrations = switching cost
