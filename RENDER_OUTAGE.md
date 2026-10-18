# Why the TruthVortex API keeps stopping on Render, and how to fix it

Written 2026-10-18, while connecting the new domain `red4ce.com`.

## Short version

The site shows no news because **the API's database no longer exists**.
Render's free plan deletes a Postgres database after its free period ends.
The API can't start without its database, so Render keeps marking it unhealthy.

There's a second, smaller problem. On the free plan, Render **puts the API to
sleep after 15 minutes with no visitors**. That makes the first visit slow, and
it stops the news scraper.

The fix is a database that doesn't expire. A way to keep the API awake is
optional.

---

## How the pieces fit together

```
Visitor ──> red4ce.com (Vercel, Next.js frontend)
               │  fetches news from
               v
            truthvortex-api.onrender.com (Render, FastAPI, free plan)
               │  reads/writes articles
               v
            Postgres database (was: Render free Postgres, now deleted)
```

- **Frontend:** Vercel project `truthvortex`, root directory `frontend/`. It's
  working, and `red4ce.com` and `www.red4ce.com` both point at it.
- **API:** Render service `truthvortex-api` (`srv-d9f544pkh4rs73d5gb0g`), free
  plan, Oregon region. It also runs the news scraper as a background thread
  every 30 minutes (`backend/main.py`, `_start_background_scraper`).
- **Database:** the API's `DATABASE_URL` points at the Render Postgres host
  `dpg-da67f0u7bikc73b47jog-a`. **That database is gone.** `render postgres list`
  returns an empty list, and this account has only one workspace.

---

## What's happening (the evidence)

### 1. The database was deleted

Every time the API starts, the log shows:

```
WARNING truthvortex ensure_schema failed (will retry on demand): could not translate host name "dpg-da67f0u7bikc73b47jog-a" to address: Name or service not known
ERROR truthvortex Background scraper error: could not translate host name "dpg-da67f0u7bikc73b47jog-a" to address: Name or service not known
```

"Could not translate host name" means the database's address doesn't exist.
The database has been removed, not just slowed down.

Render's free-tier rules (from https://render.com/docs/free):

- "Free Render Postgres databases expire 30 days after creation."
- After that you get "14 days to upgrade it to a paid compute plan". Then the
  database is **deleted, with its data**.
- Only one free Postgres database can be active per workspace.

So any free Render database dies at most about 44 days after it's created.
Creating another free one only restarts that countdown.

### 2. Render rejects every new deploy

The API's `/health` endpoint (`backend/main.py`, `health()`) runs `SELECT 1` on
the database. If the database can't be reached, it returns **HTTP 503**. That's
deliberate, so the platform knows the API is broken.

Render calls `/health` after each deploy. The new version never reaches 200, so
Render gives up and marks the deploy failed:

| Deploy | Date | Result |
|---|---|---|
| `dep-dafe62h42hec73d6cbpg` | 2026-09-07 | live (last good deploy) |
| `dep-datmvtvf3r2c73dtv77g` | 2026-09-29 | **update_failed** |
| `dep-dbaadp5g1s2s73bcm4f0` | 2026-10-18 | **update_failed** (health checks returned 503 for ~18 min) |

This is why "Render keeps stopping the API". Render isn't stopping it at
random. Every deploy fails its health check because the database is missing.
The 2026-09-29 failure means the database was most likely gone by then, so the
site has probably shown no news since about late September.

### 3. The free web service sleeps when idle

Also from Render's free-tier rules:

- A free web service "that goes 15 minutes without receiving any inbound
  traffic" spins down, and waking it takes "about one minute".
- Each workspace gets **750 free instance hours per month**. If they run out,
  Render "suspends all of your Free web services until the start of the next
  month."

What this means for TruthVortex:

- The first visitor after a quiet period waits about a minute for any news.
- **The scraper stops while the API sleeps.** It's a thread inside the API
  process, so no visitors means no new articles.
- `render.yaml` describes a separate `truthvortex-scraper` cron job, but **cron
  jobs aren't free on Render**, and that service was never created. The account
  only has `truthvortex-api` and `BunkMax`. The API's background thread is
  therefore the only scraper. Leave `DISABLE_BACKGROUND_SCRAPER` **unset** on
  the API, even though `render.yaml` sets it to `"true"`. Setting it would stop
  all scraping.
- `BunkMax` is also a free web service in the same workspace and shares the
  same 750 hours.

---

## How to fix it

### Step 1 (required): a database that doesn't expire

Pick one option.

#### Option A: Neon free Postgres (recommended, free)

Neon's free plan is "permanent (not a trial); no credit card required". It
gives 1 GB per project, which is plenty, because the scraper deletes articles
older than 2 days (`ARTICLE_RETENTION_DAYS=2`). The database sleeps after 5
minutes idle and wakes on the next query in about a second.

1. Sign up at https://neon.tech.
2. Create a project. Pick the region **AWS US West 2 (Oregon)** so the database
   sits close to the Render API, which runs in Oregon.
3. On the project dashboard, click **Connect** and copy the connection string.
   It looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxxx.us-west-2.aws.neon.tech/neondb?sslmode=require
   ```
   Keep `?sslmode=require` at the end. Treat this string as a password, because
   anyone who has it can read and change your data.
4. In the Render dashboard, open **truthvortex-api**, then **Environment**. Set
   `DATABASE_URL` to that string and click **Save Changes**. Render redeploys
   the API automatically.
5. Nothing else is needed. On startup the API creates the `news` table itself
   (`ensure_schema()` in `backend/main.py`), and the background scraper fills
   it with articles within a few minutes.

#### Option B: Render paid Postgres

Create a Postgres database on a paid plan in the Render dashboard (see
https://render.com/pricing). Copy its **Internal Database URL** into the API's
`DATABASE_URL`. Paid databases don't expire. This needs a card on file.

#### Not recommended: another free Render Postgres

It works for at most about 44 days, then this outage happens again and all the
data is deleted.

### Step 2 (optional): keep the API awake

Without this, the site works, but the first visitor after a quiet period waits
about a minute, and news only updates while people are visiting.

- **Free:** have a free uptime monitor, such as UptimeRobot, call
  `https://truthvortex-api.onrender.com/health` every 10 minutes. The API never
  goes 15 minutes without traffic, so it never sleeps and the scraper keeps
  running.
  - Cost: one always-on service uses about 744 of the 750 free hours in a
    31-day month. **Don't keep BunkMax awake the same way**, because two
    always-on free services would use up the hours, and Render would then
    suspend both until the next month.
- **Paid:** move `truthvortex-api` to a paid instance type. Paid instances never
  sleep, and the 750-hour limit no longer applies to it.

### Step 3: check that it works

```bash
# Should print {"status":"ok"}
curl https://truthvortex-api.onrender.com/health

# Should print a JSON list of articles (may be [] for the first few minutes)
curl 'https://truthvortex-api.onrender.com/news?limit=1'
```

Then open https://red4ce.com. News should appear within a few minutes of the
first successful start.

---

## Already done on 2026-10-18 (domain setup)

These work, and don't need changing again:

- GoDaddy DNS: `A @ 76.76.21.21` and `CNAME www cname.vercel-dns.com`.
- Vercel: `red4ce.com` and `www.red4ce.com` added to the `truthvortex` project.
  `NEXT_PUBLIC_SITE_URL` is set to `https://red4ce.com` for Production, and the
  site was redeployed.
- Render: `CORS_ALLOW_ORIGINS` on `truthvortex-api` is set to
  `https://red4ce.com,https://www.red4ce.com,https://truthvortex.vercel.app,https://truthvortex-sigma.vercel.app`.
  The API's startup log confirms it loaded this list.

## Temporary fix applied on 2026-10-18 (free Render Postgres again)

- Created a new free Render Postgres database, `truthvortex-db`
  (`dpg-dbafb2jncjis73dc1360-a`, Oregon, Postgres 18), and pointed the API's
  `DATABASE_URL` at its internal connection string.
- Deploy `dep-dbafg4tg1s2s73btt6cg` went live, `/health` returns
  `{"status":"ok"}`, and the scraper refilled the site with articles.
- **This database expires on 2026-11-17** and is deleted 14 days later, around
  2026-12-01. Do Step 1 (Neon or paid Postgres) before 2026-11-17, or the site
  goes empty again.
