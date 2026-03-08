"""
main.py — Orchestrator for the Morning Intelligence Brief.

Runs the full pipeline:
    1. Fetch and rank articles from RSS feeds
    2. Generate the daily brief via Claude
    3. Log the result

Usage:
    python scripts/main.py
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "outputs"

# Add project root to path so imports work from any working directory
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch import fetch_and_rank_articles
from scripts.generate_brief import generate_brief
from scripts.publish_html import publish_brief_html
from scripts.history import save_today


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


def run():
    """Run the full Morning Intelligence Brief pipeline."""
    logger = setup_logging()
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"=== Morning Intelligence Brief — {today} ===")

    # Step 1: Fetch articles
    try:
        articles = fetch_and_rank_articles()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return False

    if not articles:
        logger.error("No articles fetched. Aborting.")
        return False

    logger.info(f"Fetched {len(articles)} top articles")

    # Step 2: Generate brief
    try:
        markdown, out_path = generate_brief(articles)
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        return False

    if not markdown:
        logger.error("Brief generation returned empty. Check API key and logs.")
        return False

    logger.info(f"Brief saved to: {out_path}")
    logger.info(f"Brief length: {len(markdown)} chars")

    # Step 3: Publish HTML + widget data
    try:
        html_path = publish_brief_html(markdown, push_to_git=True)
        logger.info(f"HTML published: {html_path}")
    except Exception as e:
        logger.warning(f"HTML publish failed (non-fatal): {e}")

    # Step 4: Save today's brief to history (for dedup on future runs)
    try:
        save_today(markdown)
        logger.info("History updated")
    except Exception as e:
        logger.warning(f"History save failed (non-fatal): {e}")

    logger.info(f"=== Complete ===")
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
