"""
history.py — Rolling 7-day memory for the Daily Brief.

Tracks headlines and key topics from recent briefs so the system avoids
repeating the same stories day after day. Stored in data/history.json.

Usage:
    from scripts.history import load_history, save_today, get_recent_context
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = PROJECT_ROOT / "data" / "history.json"


def load_history():
    """
    Load history file. Returns dict keyed by date string:
    {
        "2026-03-07": {
            "headlines": ["Iran Hormuz blockade...", "US jobs report..."],
            "topics": ["Iran", "oil prices", "jobs report", "Fed"],
            "summary": "Brief covered Iran-Hormuz oil crisis..."
        },
        ...
    }
    """
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(history):
    """Save history dict, pruning entries older than 7 days."""
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in history.items() if k >= cutoff}

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(pruned, f, indent=2, ensure_ascii=False)

    print(f"  History saved ({len(pruned)} days)")


def save_today(brief_markdown):
    """
    Extract headlines and topics from today's brief and save to history.
    Called after a successful brief generation.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    history = load_history()

    headlines = _extract_headlines(brief_markdown)
    topics = _extract_topics(headlines)
    summary = _build_summary(brief_markdown)

    history[today] = {
        "headlines": headlines,
        "topics": topics,
        "summary": summary,
    }

    save_history(history)


def _extract_headlines(markdown):
    """Pull concise headline labels from the brief markdown."""
    headlines = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        for prefix in ["- ", "* ", "• "]:
            if stripped.startswith(prefix):
                text = stripped[len(prefix):]
                # Strip bold markers
                text = text.replace("**", "")
                # Take just the lead phrase (before first colon)
                if ": " in text:
                    text = text[:text.index(": ")]
                # Cap length — we only need enough for similarity matching
                text = text.strip()[:120]
                if text:
                    headlines.append(text)
                break
    return headlines


def _extract_topics(headlines):
    """Pull key topic phrases from headlines for quick matching."""
    # Simple approach: split on common delimiters and take meaningful chunks
    topics = set()
    for h in headlines:
        # Add the full headline as a topic
        topics.add(h.lower())
        # Also add individual significant words/phrases
        for word in h.split():
            word = word.strip("()[],.;:").lower()
            if len(word) > 4 and word not in {"about", "their", "these", "those", "would", "could", "should", "after", "before", "under", "which", "where", "while"}:
                topics.add(word)
    return list(topics)[:30]  # cap to keep it manageable


def is_headline_stale(title, history, threshold=0.65):
    """
    Check if a headline is too similar to one from the last 7 days.
    Returns (is_stale, similarity_score).
    """
    title_lower = title.lower()
    max_sim = 0.0

    for day_data in history.values():
        for old_headline in day_data.get("headlines", []):
            sim = SequenceMatcher(None, title_lower, old_headline.lower()).ratio()
            if sim > max_sim:
                max_sim = sim

    return max_sim >= threshold, max_sim


def get_recent_context(max_days=3):
    """
    Build a short context string for the Claude prompt showing what
    was covered in the last few days. Keeps it concise to minimize tokens.
    """
    history = load_history()
    if not history:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    lines = []

    # Get the most recent days (up to max_days), excluding today
    sorted_dates = sorted(history.keys(), reverse=True)
    recent_dates = [d for d in sorted_dates if d < today][:max_days]

    for date in recent_dates:
        day_data = history[date]
        summary = day_data.get("summary", "")
        if summary:
            lines.append(f"- {date}: {summary}")

    if not lines:
        return ""

    context = "RECENT BRIEFS (do not repeat these stories unless there is a meaningful new development — if revisiting a topic, lead with what's new):\n"
    context += "\n".join(lines)
    return context


def _build_summary(markdown):
    """
    Build a concise summary of the brief for context passing.
    Pulls headline labels from all sections, keeps it short.
    """
    all_headlines = _extract_headlines(markdown)
    # Take just the short label headlines (skip full-sentence ones)
    short = [h for h in all_headlines if len(h) < 60][:8]

    if short:
        return "Covered: " + "; ".join(short)
    return ""
