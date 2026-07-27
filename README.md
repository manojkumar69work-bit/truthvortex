# TruthVortex

A TV-style news aggregator: **FastAPI + PostgreSQL** backend with a
**multi-provider AI summarization** pipeline and a **Next.js 15 + React 19 +
Tailwind v4** frontend. Articles are fetched from curated RSS feeds, summarized
into **5–8 line Telugu** summaries, and displayed on a fixed single-screen
desktop dashboard and a scrollable mobile layout.

```
TruthVortex/
├─ backend/      FastAPI API (main.py) + scraper (scraper.py) + shared db/categories
│  └─ .env            Local config (git-ignored)
├─ frontend/     Next.js app
│  └─ .env.local      Frontend config (git-ignored)
├─ render.yaml   Render blueprint (reference)
└─ RAILWAY_DEPLOY.md  Railway deploy guide (reference)
```

## Live deployment

| Component | URL |
|-----------|-----|
| **Frontend** | https://truthvortex-sigma.vercel.app |
| **API** | https://truthvortex-api.onrender.com |
| **Database** | Render Postgres (managed) |

## How it works

1. **Scrape** — RSS feeds are fetched from ~30 curated sources across 5 categories:
   Breaking, Business, Sports, Movies, Crime.
2. **Summarize** — Each article's full text is sent through an AI pipeline that
   generates a 5–8 line Telugu summary directly.
3. **Serve** — A FastAPI endpoint (`GET /news`) returns the articles sorted by
   publish date. The Next.js frontend polls every 60s and renders them in a
   TV-style dashboard with auto-rotating sections.

## AI pipeline

### Multi-provider fallback chain

```
OpenRouter (primary) → OpenRouter2 (key rotation) → NVIDIA (fallback 1) → Groq (fallback 2)
```

When a provider hits rate limits or auth errors, the next one is tried
automatically. Articles are stored with `"Not available"` as the summary only
when all providers are exhausted.

| Provider | Model |
|----------|-------|
| **OpenRouter** | `google/gemma-4-26b-a4b-it:free` |
| **NVIDIA** | `nvidia/llama-3.3-nemotron-super-49b-v1.5` |
| **Groq** | `meta-llama/llama-4-scout-17b-16e-instruct` |

Summaries are generated **directly in Telugu** by the AI model — no Google
Translate pipeline needed.

## Local development

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL running locally

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # fill in API keys + DB settings
uvicorn main:app --reload      # http://127.0.0.1:8000
python scraper.py              # one ingestion run
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local     # defaults point at http://127.0.0.1:8000
npm run dev                    # http://localhost:3000
```

### Checking feeds

```bash
cd backend && .venv/bin/python check_feeds.py
```

## Environment variables

### Backend (`backend/.env`)

| Var | Required | Notes |
|-----|----------|-------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENROUTER_API_KEY` | Recommended | Primary AI provider |
| `OPENROUTER_API_KEY_2` | No | Secondary key for rate-limit rotation |
| `OPENROUTER_MODEL` | No | `google/gemma-4-26b-a4b-it:free` (default) |
| `NVIDIA_API_KEY` | No | Fallback AI provider |
| `GROQ_API_KEY` | No | Last-resort fallback |
| `AI_PROVIDER` | No | `openrouter` (default) |
| `CORS_ALLOW_ORIGINS` | No | Comma-separated origins |
| `MAX_CONCURRENT_SOURCES` | No | `5` on Render, `1` local (default) |
| `SCRAPE_API_TOKEN` | No | Bearer token for `/scrape` endpoint |
| `SCRAPER_INTERVAL_MINUTES` | No | `30` (default) |
| `ARTICLE_RETENTION_DAYS` | No | `2` (default); `0` keeps articles forever |

### Frontend (`frontend/.env.local`)

| Var | Required | Notes |
|-----|----------|-------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend base URL (without `/news`) |
| `NEXT_PUBLIC_SITE_URL` | No | Public URL for SEO/OG metadata |

## Features

- **Telugu AI summaries** (5–8 lines) direct from LLM
- **Multi-provider fallback** (OpenRouter → NVIDIA → Groq) for reliability
- **Background auto-scraper** runs every 30 minutes
- **2-day retention** — each cycle deletes articles older than
  `ARTICLE_RETENTION_DAYS` (2) and skips feed entries already that old
- **Light/dark theme toggle**, persisted to `localStorage`, respects OS preference
- **Preview → detail** article view with prev/next navigation (keyboard arrows,
  touch swipe) and Share button (Web Share API + clipboard fallback)
- **Auto-rotating sections** — Breaking, Business, Sports, Crime, Movies
- **Truncation-safe** summaries — retry chain ensures complete output
- **Copyright-safe images** — placeholder by default; opt-in with
  `SAFE_IMAGES_ONLY=false`
- Loading skeletons, error and empty states, branded 404, favicon, OG metadata
- Per-IP rate limiting, security headers, parameterized SQL, strict CORS

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Service banner |
| `GET /health` | Readiness probe (200=ok, 503=DB down) |
| `GET /news?limit=N` | Latest N articles (default 150) |
| `GET /news/{category}` | Articles in a single category |
| `GET /search?q=...` | ILIKE search across title/summary/source |
| `POST /scrape` | Trigger scraper (auth: `Bearer <SCRAPE_API_TOKEN>`) |

## ⚠️ Before you deploy (security)

1. **Keep secrets out of git.** `.env` and `.env.*` are already in `.gitignore`
   (only `.env.example` is tracked).
2. **Rotate any key that was ever committed.** If you previously committed a
   key, treat it as compromised and generate a new one.
3. **Never put secrets in `NEXT_PUBLIC_*`** — those are exposed to the browser.
4. **Lock down CORS.** Set `CORS_ALLOW_ORIGINS` to your real frontend origin(s);
   never use `*` in production.
