import os
import re
import html
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# Make `backend/` importable when this script is run from the repo root.
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from db import get_cursor

load_dotenv()

# =========================
# CONFIG
# =========================
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY") or os.getenv("NVAPI_KEY")

MODEL_NAME = "nvidia/llama-3.3-nemotron-super-49b-v1.5"
BATCH_SIZE = 25
SLEEP_BETWEEN_REQUESTS = 0.8
SLEEP_BETWEEN_BATCHES = 2
MIN_TEXT_LENGTH = 40
MAX_RETRIES = 2

# =========================
# AI CLIENT
# =========================
if not NVIDIA_API_KEY:
    raise ValueError("NVIDIA_API_KEY or NVAPI_KEY not found in .env")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)

# =========================
# HELPERS
# =========================
def clean_html_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_ai_summary(title: str, text: str) -> str:
    clean_title = clean_html_text(title)
    clean_text = clean_html_text(text)

    if len(clean_text) < MIN_TEXT_LENGTH:
        return ""

    prompt = f"""
Summarize this news article in the SAME language as the input.

Rules:
- Write only the summary.
- Do not write introductions like 'Here is a summary'.
- Write 5 to 8 short lines.
- No bullet points.
- No headings.
- Keep it factual and easy to read.
- Do not repeat the title.
- Focus on what happened, who is involved, and why it matters.

Title:
{clean_title}

Article:
{clean_text}
""".strip()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "/no_think"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                top_p=0.95,
                max_tokens=280,
                stream=False,
            )

            content = response.choices[0].message.content if response.choices else ""
            summary = clean_html_text(content)

            # Remove common unwanted intro line if model still adds it
            summary = re.sub(
                r"^(here is.*?summary.*?:\s*)",
                "",
                summary,
                flags=re.IGNORECASE,
            ).strip()

            return summary

        except Exception as e:
            print(f"    [AI Error attempt {attempt}/{MAX_RETRIES}]: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return ""


def get_conn():
    """Backwards-compat shim: callers below use get_cursor() instead."""
    raise NotImplementedError("use get_cursor() context manager instead")


def fetch_unsummarized_rows(limit: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, title, COALESCE(summary, '')
            FROM news
            WHERE (ai_summary IS NULL OR ai_summary = '')
              AND (summary IS NOT NULL AND summary != '')
            ORDER BY id ASC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def update_summary(db_id: int, ai_summary: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE news SET ai_summary = %s WHERE id = %s",
            (ai_summary, db_id),
        )


def count_remaining() -> int:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM news
            WHERE (ai_summary IS NULL OR ai_summary = '')
              AND (summary IS NOT NULL AND summary != '')
            """
        )
        return cur.fetchone()[0]


# =========================
# MAIN BACKFILL
# =========================
def backfill_all():
    remaining_before = count_remaining()
    print("=" * 60)
    print("TruthVortex AI Backfill Starting...")
    print(f"Rows remaining before start: {remaining_before}")
    print("=" * 60)

    total_updated = 0
    total_failed = 0
    batch_no = 1

    while True:
        rows = fetch_unsummarized_rows(BATCH_SIZE)

        if not rows:
            break

        print(f"\n--- Batch {batch_no} | rows fetched: {len(rows)} ---")

        for db_id, title_text, summary_text in rows:
            print(f"ID {db_id}: {title_text[:70]}")

            context_text = f"Title: {title_text}\nContent: {summary_text}"
            ai_sum = generate_ai_summary(title_text, context_text)

            if ai_sum:
                try:
                    update_summary(db_id, ai_sum)
                    total_updated += 1
                    print(f"  ✓ Updated ID {db_id}")
                except Exception as e:
                    total_failed += 1
                    print(f"  ✗ DB update failed for ID {db_id}: {e}")
            else:
                total_failed += 1
                print(f"  ✗ No summary generated for ID {db_id}")

            time.sleep(SLEEP_BETWEEN_REQUESTS)

        batch_no += 1
        time.sleep(SLEEP_BETWEEN_BATCHES)

    remaining_after = count_remaining()

    print("\n" + "=" * 60)
    print("Backfill complete")
    print(f"Updated rows : {total_updated}")
    print(f"Failed rows  : {total_failed}")
    print(f"Still empty  : {remaining_after}")
    print("=" * 60)


if __name__ == "__main__":
    backfill_all()