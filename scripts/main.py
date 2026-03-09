"""
main.py — Orchestrator for the Morning Intelligence Brief.

Runs the full pipeline:
    1. Fetch and rank articles from RSS feeds
    2. Generate the daily brief via Claude
    3. Publish HTML + widget JSON
    4. Save to history
    5. Send email digest
    6. Log result to runs.log

Usage:
    python scripts/main.py
"""

import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "outputs"
RUNS_LOG = PROJECT_ROOT / "data" / "runs.log"

# Add project root to path so imports work from any working directory
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch import fetch_and_rank_articles
from scripts.generate_categories import generate_categories
from scripts.emailer import send_brief_emails


def setup_logging():
    """Set up logging to both console and a log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "run.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    return logging.getLogger(__name__)


def log_run(status, details=""):
    """Append a one-line entry to data/runs.log for quick health checks."""
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{ts}  {status:10s}  {details}\n"
    with open(RUNS_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def already_ran_today(today: str) -> bool:
    """Check Supabase to see if today's categories were already generated."""
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        return False
    try:
        client = create_client(url, key)
        result = client.table("daily_categories").select("date").eq("date", today).limit(1).execute()
        return bool(result.data)
    except Exception:
        return False


def run():
    """Run the full Daily News pipeline."""
    logger = setup_logging()
    today = datetime.now().strftime("%Y-%m-%d")
    start = datetime.now()

    logger.info(f"=== Daily News Pipeline — {today} ===")

    # Skip if today's categories already exist in Supabase
    if already_ran_today(today):
        logger.info(f"Categories already generated for {today} — skipping.")
        log_run("SKIPPED", f"Already ran for {today}")
        return True

    # Step 1: Fetch and rank articles
    try:
        articles, all_articles = fetch_and_rank_articles()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        log_run("FAILED", f"Fetch error: {e}")
        return False

    if not all_articles:
        logger.error("No articles fetched. Aborting.")
        log_run("FAILED", "No articles fetched")
        return False

    logger.info(f"Fetched {len(all_articles)} articles")

    # Step 2: Generate structured category data (full article pool)
    try:
        cat_data, cat_path = generate_categories(all_articles)
        if cat_data:
            logger.info(f"Category data saved: {cat_path}")
        else:
            logger.error("Category generation returned empty.")
            log_run("FAILED", "Empty category data from API")
            return False
    except Exception as e:
        logger.error(f"Category generation failed: {e}")
        log_run("FAILED", f"Category error: {e}")
        return False

    # Step 3: Send email digest
    try:
        send_brief_emails(today)
        logger.info("Emails sent")
    except Exception as e:
        logger.warning(f"Email send failed (non-fatal): {e}")

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"=== Complete in {elapsed:.1f}s ===")
    log_run("OK", f"{len(all_articles)} articles, {elapsed:.1f}s")
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
