# ─── TruthVortex API / scraper image ───────────────────────────
# Used by both the web service (uvicorn) and the cron scraper.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2-binary ships its own libpq, so no build toolchain is needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Web service entrypoint. The cron job overrides this with `python scraper.py`.
# --proxy-headers + --forwarded-allow-ips so per-IP rate limiting uses the real
# client IP (X-Forwarded-For) behind Render's reverse proxy, not the proxy IP.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
