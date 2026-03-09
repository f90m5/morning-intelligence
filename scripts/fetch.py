"""
fetch.py — Pull articles from RSS feeds, clean, deduplicate, and rank them.

Usage:
    from scripts.fetch import fetch_and_rank_articles
    articles = fetch_and_rank_articles()  # returns list of top-ranked article dicts
"""

import json
import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from difflib import SequenceMatcher

import feedparser
import requests

# Project root (one level up from scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def load_sources():
    """Load RSS feed config from sources.json."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_all_feeds(sources):
    """
    Fetch articles from all RSS feeds.
    Returns a flat list of article dicts.
    """
    all_articles = []
    max_per_feed = sources.get("max_articles_per_feed", 8)

    for feed_cfg in sources["rss_feeds"]:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        category = feed_cfg["category"]
        tier = feed_cfg["tier"]

        try:
            # feedparser handles both RSS and Atom
            parsed = feedparser.parse(url)

            if parsed.bozo and len(parsed.entries) == 0:
                print(f"  [SKIP] {name}: feed error")
                continue

            count = 0
            for entry in parsed.entries[:max_per_feed]:
                article = parse_entry(entry, name, category, tier)
                if article:
                    all_articles.append(article)
                    count += 1

            print(f"  [OK]   {name}: {count} articles")

        except Exception as e:
            print(f"  [ERR]  {name}: {e}")

    return all_articles


def parse_entry(entry, source_name, category, tier):
    """
    Extract a clean article dict from a feedparser entry.
    Returns None if the entry is unusable.
    """
    title = clean_text(entry.get("title", ""))
    if not title:
        return None

    # Get description/summary — strip HTML tags
    description = clean_text(entry.get("summary", entry.get("description", "")))

    # Get link
    link = entry.get("link", "")

    # Get published date
    published = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass

    return {
        "title": title,
        "description": description[:500],  # cap length
        "link": link,
        "source": source_name,
        "category": category,
        "tier": tier,
        "published": published.isoformat() if published else None,
    }


def clean_text(text):
    """Strip HTML tags, extra whitespace, and common junk from text."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove HTML entities
    text = re.sub(r"&\w+;", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def filter_recent(articles, hours=48):
    """Keep only articles published within the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    no_date = []

    for a in articles:
        if a["published"]:
            try:
                pub = datetime.fromisoformat(a["published"])
                if pub >= cutoff:
                    recent.append(a)
            except Exception:
                no_date.append(a)
        else:
            # No date — keep it (some feeds don't include dates)
            no_date.append(a)

    # Include undated articles but mark them
    return recent + no_date


def deduplicate(articles, threshold=0.7):
    """
    Remove near-duplicate articles based on headline similarity.
    Keeps the version from the higher-tier source.
    """
    # Sort by tier descending so we keep higher-tier versions
    sorted_articles = sorted(articles, key=lambda a: a["tier"], reverse=True)
    seen_urls = set()
    kept = []

    for article in sorted_articles:
        # Exact URL match
        if article["link"] in seen_urls:
            continue
        seen_urls.add(article["link"])

        # Fuzzy headline match against already-kept articles
        is_dupe = False
        for kept_article in kept:
            similarity = SequenceMatcher(
                None,
                article["title"].lower(),
                kept_article["title"].lower(),
            ).ratio()
            if similarity >= threshold:
                is_dupe = True
                break

        if not is_dupe:
            kept.append(article)

    return kept


def rank_articles(articles, history=None):
    """
    Score and rank articles. Higher score = more important.

    Scoring:
        - tier (1-3): tier * 2 points  (max 6)
        - has description: +2
        - keyword boost: +3 for high-signal terms
        - staleness penalty: -4 if headline is too similar to recent days
    """
    from scripts.history import is_headline_stale

    keywords_high = [
        "earnings", "revenue", "profit", "gdp", "inflation", "fed ",
        "regulation", "ipo", "acquisition", "merger", "layoff",
        "ai ", "artificial intelligence", "machine learning", "data",
        "cloud", "cybersecurity", "startup", "funding",
        "market", "stock", "economy", "trade", "tariff",
        "sanctions", "nato", "military", "conflict", "treaty",
        "diplomacy", "geopolit", "nuclear", "alliance", "embargo",
    ]

    if history is None:
        history = {}

    for article in articles:
        score = 0

        # Tier score
        score += article["tier"] * 2

        # Has a meaningful description
        if len(article.get("description", "")) > 50:
            score += 2

        # Keyword boost
        text = (article["title"] + " " + article.get("description", "")).lower()
        for kw in keywords_high:
            if kw in text:
                score += 3
                break  # only one keyword boost per article

        # Staleness penalty — deprioritize headlines we've already covered
        if history:
            stale, sim = is_headline_stale(article["title"], history)
            if stale:
                score -= 4
                article["stale"] = True
                article["stale_sim"] = round(sim, 2)

        article["score"] = score

    # Sort by score descending
    articles.sort(key=lambda a: a["score"], reverse=True)
    return articles


def select_balanced(ranked_articles, max_total, sources_config):
    """
    Pick top articles while ensuring category diversity.

    Strategy: guarantee at least 2 articles from each category that has content,
    then fill remaining slots with the highest-scored articles overall.
    """
    categories = sources_config.get("categories", [])
    min_per_category = 2
    selected = []
    selected_links = set()

    # Phase 1: pick top articles from each category
    for cat in categories:
        cat_articles = [a for a in ranked_articles if a["category"] == cat]
        count = 0
        for article in cat_articles:
            if count >= min_per_category:
                break
            if article["link"] not in selected_links:
                selected.append(article)
                selected_links.add(article["link"])
                count += 1

    # Phase 2: fill remaining slots with best overall (any category)
    for article in ranked_articles:
        if len(selected) >= max_total:
            break
        if article["link"] not in selected_links:
            selected.append(article)
            selected_links.add(article["link"])

    # Re-sort final selection by score
    selected.sort(key=lambda a: a["score"], reverse=True)
    return selected


def save_articles(articles, stage="raw"):
    """Save articles to a JSON file with today's date."""
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR if stage == "raw" else PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{today}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    print(f"  Saved {len(articles)} articles to {out_path.name}")
    return out_path


def fetch_and_rank_articles():
    """
    Main entry point. Runs the full pipeline:
        fetch → filter recent → deduplicate → rank (with history) → save → return top N

    Returns a tuple: (top_articles, all_ranked_articles)
      - top_articles: balanced selection of max_total for the personal brief
      - all_ranked_articles: full deduplicated + ranked set for category generation
        (gives each of the 12 product categories enough articles to work with)
    """
    from scripts.history import load_history

    print("\n--- Fetching articles ---")
    sources = load_sources()
    max_total = sources.get("max_total_articles", 25)

    # Load 7-day history for staleness checks
    history = load_history()
    if history:
        print(f"  Loaded {len(history)} days of history for dedup")

    # 1. Fetch from all feeds
    all_articles = fetch_all_feeds(sources)
    print(f"\n  Total fetched: {len(all_articles)}")

    # 2. Save raw
    save_articles(all_articles, stage="raw")

    # 3. Filter to recent articles (last 48 hours)
    recent = filter_recent(all_articles, hours=48)
    print(f"  After recency filter: {len(recent)}")

    # 4. Deduplicate
    unique = deduplicate(recent)
    print(f"  After deduplication: {len(unique)}")

    # 5. Rank (with history-based staleness penalty)
    ranked = rank_articles(unique, history=history)
    stale_count = sum(1 for a in ranked if a.get("stale"))
    if stale_count:
        print(f"  {stale_count} articles penalized as stale (similar to recent briefs)")

    # 6. Select balanced mix for personal brief
    top = select_balanced(ranked, max_total, sources)
    print(f"  Top {len(top)} articles selected for brief (balanced across categories)")
    print(f"  Full pool: {len(ranked)} articles available for category generation")

    # 7. Save processed (top articles for brief)
    save_articles(top, stage="processed")

    print("--- Fetch complete ---\n")
    return top, ranked


# Allow running standalone for testing
if __name__ == "__main__":
    articles = fetch_and_rank_articles()
    for i, a in enumerate(articles[:5], 1):
        print(f"  {i}. [{a['category']}] {a['title']}")
        print(f"     Source: {a['source']} | Tier: {a['tier']} | Score: {a['score']}")
        print()
