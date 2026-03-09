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
from scripts.generate_brief import generate_brief
from scripts.generate_categories import generate_categories
from scripts.publish_html import publish_brief_html
from scripts.history import save_today
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


def run():
    """Run the full Morning Intelligence Brief pipeline."""
    logger = setup_logging()
    today = datetime.now().strftime("%Y-%m-%d")
    start = datetime.now()

    logger.info(f"=== Morning Intelligence Brief — {today} ===")

    # Skip if today's brief already exists
    existing = PROJECT_ROOT / "outputs" / "briefs" / f"{today}.md"
    if existing.exists():
        logger.info(f"Brief already exists for {today} — skipping. Delete {existing.name} to regenerate.")
        log_run("SKIPPED", f"Brief already exists for {today}")
        return True

    # Step 1: Fetch articles
    try:
        articles, all_articles = fetch_and_rank_articles()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        log_run("FAILED", f"Fetch error: {e}")
        return False

    if not articles:
        logger.error("No articles fetched. Aborting.")
        log_run("FAILED", "No articles fetched")
        return False

    logger.info(f"Fetched {len(articles)} top articles for brief, {len(all_articles)} total for categories")

    # Step 2: Generate brief (uses top 25 for quality + cost control)
    try:
        markdown, out_path = generate_brief(articles)
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        log_run("FAILED", f"Generation error: {e}")
        return False

    if not markdown:
        logger.error("Brief generation returned empty. Check API key and logs.")
        log_run("FAILED", "Empty brief from API")
        return False

    logger.info(f"Brief saved to: {out_path}")
    logger.info(f"Brief length: {len(markdown)} chars")

    # Step 3: Generate structured category data (uses full article pool for coverage)
    try:
        cat_data, cat_path = generate_categories(all_articles)
        if cat_data:
            logger.info(f"Category data saved: {cat_path}")
        else:
            logger.warning("Category generation returned empty (non-fatal)")
    except Exception as e:
        logger.warning(f"Category generation failed (non-fatal): {e}")

    # Step 4: Publish HTML + widget data
    # Skip git push when running in CI (GitHub Actions sets CI=true automatically)
    in_ci = os.getenv("CI", "").lower() == "true"
    try:
        html_path = publish_brief_html(markdown, push_to_git=not in_ci)
        logger.info(f"HTML published: {html_path}")
    except Exception as e:
        logger.warning(f"HTML publish failed (non-fatal): {e}")

    # Step 5: Save today's brief to history (for dedup on future runs)
    try:
        save_today(markdown)
        logger.info("History updated")
    except Exception as e:
        logger.warning(f"History save failed (non-fatal): {e}")

    # Step 6: Send personalised email digest to all users
    try:
        send_brief_emails(today)
        logger.info("Emails sent")
    except Exception as e:
        logger.warning(f"Email send failed (non-fatal): {e}")

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"=== Complete in {elapsed:.1f}s ===")
    log_run("OK", f"{len(articles)} articles, {len(markdown)} chars, {elapsed:.1f}s")
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
