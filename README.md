# TruthVortex

A TV-style news aggregator: **FastAPI + PostgreSQL** backend with an
**multi-provider AI summarization** pipeline and a **Next.js 15 + React 19 +
Tailwind v4** frontend. Articles are fetched from curated RSS feeds, summarized
into **5–8 line Telugu** summaries, and displayed on a fixed single-screen
desktop dashboard and a scrollable mobile layout.

```
Project NG/
├─ backend/      FastAPI API (main.py) + scraper (scraper.py) + shared db/categories
│  └─ .env            Local config (git-ignored)
├─ frontend/     Next.js app
│  └─ .env.local      Frontend config (git-ignored)
└─ render.yaml   Render blueprint: Postgres + API + scraper cron
```

## How it works

1. **Scrape** — RSS feeds are fetched from ~15 curated sources (UN, Guardian,
   PIB, NASA, Telangana Today, Wikinews) across 5 categories: Breaking,
   Business, Sports, Movies, Crime.
2. **Summarize** — Each article's full text is extracted, then sent through an
   AI pipeline that generates a 5–8 line English summary, which is translated
   to Telugu via Google Translate (no API key needed).
3. **Serve** — A FastAPI endpoint (`GET /news`) returns the articles sorted by
   publish date. The Next.js frontend polls every 60s and renders them in a
   TV-style dashboard with auto-rotating sections.

## AI pipeline

### Multi-provider fallback chain

```
Groq (primary) → Gemini (fallback 1) → NVIDIA (fallback 2)
```

When a provider hits rate limits or auth errors, the next one is tried
automatically. When all three are exhausted, articles are stored with
`"Not available"` as the summary.

| Provider | Model | Token limits (free) |
|----------|-------|---------------------|
| **Groq** | `meta-llama/llama-4-scout-17b-16e-instruct` | 30 RPM, 30K TPM, 1K RPD, 500K TPD |
| **Gemini** | `models/gemini-2.5-flash` | ~60 RPM, ~1,500 RPD |
| **NVIDIA** | `nvidia/llama-3.3-nemotron-super-49b-v1.5` | Undocumented (slow/rate-limited) |

Key Groq rate limits per model on the free tier:

| Model | RPM | RPD | TPM | TPD |
|-------|-----|-----|-----|-----|
| `llama-3.3-70b-versatile` | 30 | 1K | 12K | 100K |
| `meta-llama/llama-4-scout-17b-16e-instruct` (current) | 30 | 1K | **30K** | **500K** |
| `llama-3.1-8b-instant` | 30 | **14.4K** | 6K | **500K** |

At ~2,300 tokens per summary call, ~217 summaries/day on Scout/8B models.

### Translation pipeline

```
Article text → AI generates English summary → Google Translate (free) → Telugu
                                                       ↓
                                        Telugu headline & summary stored in DB
```

- English generation produces more accurate, structured output
- Google Translate (`deep_translator` library) costs nothing, no API key
- Both headline and summary are translated

### Truncation safety

- `max_tokens=2500` for summaries (12x what 8 lines need)
- If `finish_reason="length"` is hit, retries with doubled tokens
- Up to 3 retries (2500 → 5000 → 10000 → 20000)
- Only returns partial output after all 3 retries fail

## ⚠️ Before you deploy (security)

1. **Keep secrets out of git.** `.env` and `.env.*` are already in `.gitignore`
   (only `.env.example` is tracked). If a `.env` was ever committed in your
   fork, untrack it:
   ```bash
   git rm --cached .env backend/.env frontend/.env.local 2>/dev/null || true
   git commit -m "Stop tracking secrets"
   ```
2. **Rotate any key that was ever committed.** If you previously committed a
   Groq, Gemini, or NVIDIA key, treat it as compromised and generate a new one.
3. **Never put secrets in `NEXT_PUBLIC_*`** — those are exposed to the browser.
4. **Lock down CORS.** Set `CORS_ALLOW_ORIGINS` to your real frontend origin(s);
   never use `*` in production.

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
cp .env.example .env.local     # defaults point at http://127.0.0.1:8000/news
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
| `NVIDIA_API_KEY` | Yes | Primary AI provider for Telugu headline + summary generation |
| `GROQ_API_KEY` | No | Fallback AI provider (https://console.groq.com/keys) |
| `GEMINI_API_KEY` | No | Fallback provider; must start with `AIza` |
| `AI_MODEL` | No | Override NVIDIA/model name |
| `ENABLE_AI_SUMMARY` | No | `true` (default) |
| `ENABLE_TRANSLATION` | No | Not used for scraper summaries; generation is direct Telugu |
| `SUMMARY_LANGUAGE` | No | Ignored by scraper; generated headline + summary are forced to Telugu |
| `CORS_ALLOW_ORIGINS` | No | `http://localhost:3000` (default) |
| `MAX_CONCURRENT_SOURCES` | No | `1` — sequential to avoid rate limits |

### Frontend (`frontend/.env.local`)

| Var | Required | Notes |
|-----|----------|-------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend `/news` URL |
| `NEXT_PUBLIC_SITE_URL` | No | Public URL for SEO/OG metadata |

## Features

- **Telugu AI summaries** (5–8 lines) via English → Google Translate pipeline
- **Multi-provider fallback** (Groq → Gemini → NVIDIA) for reliability
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

## Production deploy

### Backend + DB + scraper → Render (via blueprint)

1. Push repo to GitHub.
2. Render: **New → Blueprint**, point at repo. `render.yaml` provisions
   Postgres, API web service, and scraper cron (every 30 min).
3. Set secrets (`sync: false`): `GROQ_API_KEY`, `GEMINI_API_KEY`,
   `CORS_ALLOW_ORIGINS`.
4. Enable `pg_trgm` for fast search:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```

Same approach works on Railway/Fly.io: one web service
(`uvicorn main:app --host 0.0.0.0 --port $PORT`) + one scheduled job
(`python scraper.py`).

### Frontend → Vercel

1. **New Project** → import repo, set **Root Directory** to `frontend`.
2. Add env vars:
   - `NEXT_PUBLIC_API_URL = https://<your-api>.onrender.com/news`
   - `NEXT_PUBLIC_SITE_URL = https://<your-app>.vercel.app`
3. Deploy. Add Vercel URL to API's `CORS_ALLOW_ORIGINS`.

## Health

`GET /health` returns `200 {"status":"ok"}` when the DB is reachable and
**`503`** otherwise — works as a real readiness probe for load balancers.

## ⚖️ Legal note

News sources are scraped for text and images that may carry logos/watermarks.
For a public launch, prefer reuse-friendly sources (Guardian Open Platform,
Wikinews, UN News, PIB) and openly licensed images, store only short summaries,
and link back to the original article.
