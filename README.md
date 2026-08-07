# TruthVortex

**Telugu news, summarized by AI, refreshed every 30 minutes.**

Most Telugu news sites are ad-heavy walls of text. TruthVortex pulls ~30 RSS sources across 5 categories, has an LLM write a 5–8 line Telugu summary of each article, and renders them as a TV-style dashboard you can read at a glance.

**🔗 [truthvortex-sigma.vercel.app](https://truthvortex-sigma.vercel.app)** · FastAPI + Postgres + Next.js 15 · live

<!-- TODO: add a screenshot here — the TV-style dashboard is the whole pitch and
     a reader can't see it from prose. ![TruthVortex dashboard](docs/screenshot.png) -->

---

## The hard part: free LLM tiers are unreliable, and the feed can't stop

A news feed that stalls is a dead product. But every free LLM tier rate-limits, and providers go down. So summarization runs through a **fallback chain** — if a provider returns a rate-limit or auth error, the next one takes over mid-run:

```
OpenRouter (primary) → OpenRouter2 (key rotation) → NVIDIA → Groq
```

An article is only stored with `"Not available"` if *all four* are exhausted. Summaries are generated **directly in Telugu** by the model — no translation hop, so no round-trip degradation.

Three more things this had to survive:

**A connection-pool race.** The background scraper and the API server competed for Postgres connections; under concurrent scrapes the pool would deadlock. Fixed by bounding concurrency (`MAX_CONCURRENT_SOURCES`, 5 on Render / 1 local) and correcting pool lifecycle.

**Free-tier storage limits.** Articles older than `ARTICLE_RETENTION_DAYS` (2) are pruned every cycle, and feed entries already that old are skipped rather than fetched. Storage stays flat instead of growing without bound.

**Duplicate stories.** ~30 sources cover the same events. Fuzzy deduplication catches near-identical stories that exact-match wouldn't.

Hardening: per-IP rate limiting, CSP and security headers, parameterized SQL, strict CORS, and a React error boundary so one bad article can't blank the page.

---

## Architecture

```
~30 RSS feeds                Background scraper (every 30 min)
      │                              │
      └──────────────────────────────┤ fuzzy dedupe
                                     │ AI summarize (4-provider fallback)
                                     │ prune > 2 days old
                                     ▼
                              Postgres (Render)
                                     │
                        FastAPI  GET /news, /news/{cat}, /search
                                     │
                        Next.js 15 frontend (Vercel) — polls every 60s
```

| Path | What's in it |
|---|---|
| [`backend/scraper.py`](backend/scraper.py) | Feed ingestion, dedupe, the provider fallback chain |
| [`backend/main.py`](backend/main.py) | API, rate limiting, security headers |
| [`backend/source_policy.py`](backend/source_policy.py) | Per-source rules and image-copyright policy |
| [`backend/db.py`](backend/db.py) | Pool management and retention pruning |

---

<details>
<summary><b>Full setup, environment variables, and API reference</b></summary>

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

</details>

---

<sub>Built by [Manoj Kumar Ethini](https://github.com/manojkumar69work-bit) · summaries are AI-generated; article text and links belong to their original publishers</sub>
