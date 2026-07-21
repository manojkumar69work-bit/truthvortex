# Deploying TruthVortex on Railway

The backend has three parts, all deployed in **one Railway project**:

1. **PostgreSQL** — Railway managed plugin (provides `DATABASE_URL`)
2. **API** — FastAPI web service (Docker, `backend/`)
3. **Scraper** — a cron service that runs `python scraper.py` every 30 min

The **frontend stays on Vercel** — you only repoint it at the new Railway API URL.

> Config-as-code lives in `backend/railway.toml` (build + healthcheck). Everything
> else is a few clicks in the dashboard.

---

## 1. Create the project + database

1. Go to <https://railway.app> → **New Project** → **Deploy PostgreSQL**.
2. Once the DB is up, note it exists — you'll reference `${{Postgres.DATABASE_URL}}` later.

## 2. Add the API (web service)

1. In the same project: **New** → **GitHub Repo** → select `manojkumar69work-bit/truthvortex`.
2. Open the new service → **Settings**:
   - **Root Directory**: `backend`
   - **Build**: Railway auto-detects the `Dockerfile` (and `railway.toml`).
   - **Healthcheck Path**: `/health` (already set by `railway.toml`).
3. **Variables** tab → add (see the full list in §4). The important one:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`  ← type this exactly; it's a reference.
4. **Settings → Networking → Generate Domain**. You get a URL like
   `https://truthvortex-api-production.up.railway.app`. Save it.

## 3. Add the scraper (cron service)

1. **New** → **GitHub Repo** → same repo again (creates a 2nd service).
2. Rename it to `truthvortex-scraper`. **Settings**:
   - **Root Directory**: `backend`
   - **Custom Start Command**: `python scraper.py`
   - **Cron Schedule**: `*/30 * * * *`  (every 30 min)
   - Under **Deploy**, turn **off** the healthcheck (cron jobs are one-shot; they
     start, run, and exit — they don't serve HTTP).
3. **Variables** tab → add the same AI + DB variables as the API (§4), plus:
   - `SAFE_IMAGES_ONLY` = `false`
   - `MAX_CONCURRENT_SOURCES` = `5`

> Tip: use Railway's **shared variables** (project level) so `DATABASE_URL` and the
> API keys are defined once and referenced by both services.

## 4. Environment variables

Set these on **both** the API and scraper services (or as shared/project variables):

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `AI_PROVIDER` | `openrouter` |
| `OPENROUTER_API_KEY` | *(your 1st OpenRouter key)* |
| `OPENROUTER_API_KEY_2` | *(your 2nd OpenRouter key)* |
| `OPENROUTER_MODEL` | `google/gemma-4-26b-a4b-it:free` |
| `GROQ_API_KEY` | *(your Groq key — fallback)* |
| `CORS_ALLOW_ORIGINS` | *(your Vercel URL, e.g. `https://your-app.vercel.app`)* — **API only** |

`GEMINI_API_KEY` / `NVIDIA_API_KEY` are optional; the app skips absent keys.
The provider fallback order is: **openrouter → openrouter2 → groq → nvidia → gemini**.

## 5. Point the frontend (Vercel) at Railway

In your Vercel project → **Settings → Environment Variables**:

- `NEXT_PUBLIC_API_URL` = `https://<your-railway-api-domain>`
  **Base URL only — do NOT append `/news`.** `frontend/src/components/constants.ts`
  already appends `/news` to this value.

Then **redeploy** the Vercel project so the new value is baked into the build.

Finally, set `CORS_ALLOW_ORIGINS` on the Railway **API** service to your exact
Vercel domain (comma-separated if you have several, e.g. preview + prod). No `*`.

## 6. Verify

```bash
# API health
curl https://<your-railway-api-domain>/health

# News endpoint returns data
curl https://<your-railway-api-domain>/news | head

# Watch the scraper: Railway dashboard → scraper service → Deployments → Logs
# You should see "Active: openrouter (google/gemma-4-26b-a4b-it:free)" and
# Telugu summaries being generated.
```

## Schema / first run

`main.py` ensures the schema on startup, and the scraper populates the DB. The
first cron run may take a few minutes. If `/news` is empty, trigger the scraper
once manually from the dashboard (scraper service → **Deploy** / run now).
