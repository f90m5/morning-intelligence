"""
generate_categories.py — Generate structured per-category JSON from today's articles.

This is the product pipeline — distinct from generate_brief.py (personal HTML brief).
Output is stored in data/categories/{date}.json AND written to Supabase.

Each category gets 3 depth levels:
  depth 1 — headline only (widget)
  depth 2 — headline + summary + bullets (medium read)
  depth 3 — full detail + why it matters + what to watch (full read)

Usage:
    from scripts.generate_categories import generate_categories
    result = generate_categories(articles)

    # or standalone:
    python scripts/generate_categories.py
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from supabase import create_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "prompts" / "category_prompt.txt"
CATEGORIES_CONFIG_PATH = PROJECT_ROOT / "config" / "categories.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "categories"

load_dotenv(PROJECT_ROOT / ".env", override=True)


def load_categories():
    """Load the 12 product categories from config."""
    with open(CATEGORIES_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["categories"]


def load_prompt_template():
    """Load the category prompt template."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def format_categories_for_prompt(categories):
    """Format the category list for injection into the prompt."""
    lines = []
    for cat in categories:
        lines.append(f"  - {cat['id']}: {cat['label']} — {cat['description']}")
    return "\n".join(lines)


def format_articles_for_prompt(articles):
    """Format articles for the prompt — same as generate_brief.py."""
    lines = []
    for i, article in enumerate(articles, 1):
        source = article.get("source", "Unknown")
        category = article.get("category", "general")
        title = article.get("title", "No title")
        desc = article.get("description", "")
        published = article.get("published", "")

        entry = f"{i}. [{category.upper()}] {title}\n"
        entry += f"   Source: {source}"
        if published:
            entry += f" | Published: {published[:10]}"
        entry += "\n"
        if desc:
            entry += f"   {desc}\n"

        lines.append(entry)
    return "\n".join(lines)


def build_prompt(articles, categories):
    """Build the full category generation prompt."""
    template = load_prompt_template()
    today = datetime.now().strftime("%B %d, %Y")
    articles_text = format_articles_for_prompt(articles)
    categories_text = format_categories_for_prompt(categories)

    prompt = template.replace("{date}", today)
    prompt = prompt.replace("{articles}", articles_text)
    prompt = prompt.replace("{categories}", categories_text)
    return prompt


def extract_json_from_response(text):
    """
    Extract JSON from Claude's response.
    Handles cases where the model wraps output in markdown code fences.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()
    return text


def recover_partial_json(text, categories):
    """
    If the response was truncated mid-JSON (hit token limit), attempt to
    salvage all complete categories by finding the last valid closing brace.
    Returns a valid data dict with however many categories completed.
    """
    cat_ids = [cat["id"] for cat in categories]
    best_data = None

    # Walk backwards through category boundaries to find valid JSON
    for cat_id in reversed(cat_ids):
        # Find the start of this category key
        marker = f'"{cat_id}"'
        idx = text.find(marker)
        if idx == -1:
            continue

        # Try to close off the JSON at every }} we can find before this point
        truncated = text[:idx].rstrip().rstrip(",").rstrip()

        # Close off the categories object and root object
        attempt = truncated + "}\n  }\n}"
        try:
            data = json.loads(attempt)
            if "categories" in data and len(data["categories"]) > 0:
                best_data = data
                recovered = list(data["categories"].keys())
                print(f"  [RECOVER] Salvaged {len(recovered)} of {len(cat_ids)} categories: {', '.join(recovered)}")
                break
        except json.JSONDecodeError:
            continue

    return best_data


def validate_structure(data, categories):
    """
    Validate that the response has all expected categories and
    at least one story per category. Returns (is_valid, list_of_issues).
    """
    issues = []
    expected_ids = {cat["id"] for cat in categories}
    returned_ids = set(data.get("categories", {}).keys())

    missing = expected_ids - returned_ids
    if missing:
        issues.append(f"Missing categories: {', '.join(sorted(missing))}")

    for cat_id, cat_data in data.get("categories", {}).items():
        stories = cat_data.get("stories", [])
        if not stories:
            issues.append(f"{cat_id}: no stories returned")
        elif not stories[0].get("headline"):
            issues.append(f"{cat_id} story 1: missing headline")

    return len(issues) == 0, issues


def call_claude(prompt, max_retries=2):
    """Call Claude API and return the raw response text."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [ERR] ANTHROPIC_API_KEY not found in .env")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    model = "claude-sonnet-4-20250514"
    max_tokens = 8192  # Sonnet's absolute maximum

    for attempt in range(max_retries):
        try:
            print(f"  Calling {model} (attempt {attempt + 1}, max_tokens={max_tokens})...")
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text
            usage = response.usage
            print(f"  Response: {len(text)} chars | Tokens: {usage.input_tokens} in, {usage.output_tokens} out")
            return text

        except anthropic.RateLimitError:
            print(f"  [WARN] Rate limited. Waiting 30s...")
            time.sleep(30)
        except anthropic.APIError as e:
            print(f"  [ERR] API error: {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in 15s...")
                time.sleep(15)
            else:
                return None
        except Exception as e:
            print(f"  [ERR] Unexpected error: {e}")
            return None

    return None


def save_categories(data, date_str=None):
    """Save the category JSON to data/categories/{date}.json."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{date_str}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  Categories saved to {out_path.name}")
    return out_path


def write_to_supabase(data, date_str):
    """
    Upsert today's category data into Supabase daily_categories table.
    Uses service role key to bypass RLS for backend writes.
    Uses upsert so re-runs overwrite cleanly without duplicates.
    """
    url = os.getenv("SUPABASE_URL")
    # Prefer service key for backend writes (bypasses RLS); fall back to anon key
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("  [SKIP] SUPABASE_URL or SUPABASE_KEY not set — skipping DB write")
        return False

    try:
        client = create_client(url, key)
        categories = data.get("categories", {})
        rows = []

        for cat_id, cat_data in categories.items():
            stories = cat_data.get("stories", [])
            # Pad to 3 slots so columns are always populated
            while len(stories) < 3:
                stories.append(None)
            # Collect all sources across stories
            all_sources = []
            for s in stories:
                if s:
                    all_sources.extend(s.get("sources", []))
            rows.append({
                "date": date_str,
                "category": cat_id,
                "category_label": cat_data.get("category_label", cat_id),
                "headline": (stories[0] or {}).get("headline", ""),
                "depth_1": stories[0],   # story 1 (always shown)
                "depth_2": stories[1],   # story 2 (shown at depth 2+)
                "depth_3": stories[2],   # story 3 (shown at depth 3)
                "sources": all_sources,
                "has_content": cat_data.get("has_content", True),
            })

        # Upsert — updates existing rows if date+category already exists
        result = client.table("daily_categories").upsert(
            rows, on_conflict="date,category"
        ).execute()

        print(f"  Supabase: {len(rows)} rows upserted to daily_categories")
        return True

    except Exception as e:
        print(f"  [WARN] Supabase write failed (non-fatal): {e}")
        return False


def generate_categories(articles):
    """
    Main entry point. Takes ranked articles, generates per-category
    structured JSON via Claude, saves to data/categories/{date}.json.

    Returns (data_dict, file_path) or (None, None) on failure.
    """
    print("\n--- Generating category data ---")

    if not articles:
        print("  [ERR] No articles provided")
        return None, None

    categories = load_categories()
    print(f"  Loaded {len(categories)} categories")

    # Build prompt
    prompt = build_prompt(articles, categories)
    print(f"  Prompt built ({len(prompt)} chars, {len(articles)} articles)")

    # Call Claude
    raw_response = call_claude(prompt)
    if not raw_response:
        print("  [ERR] No response from Claude")
        return None, None

    # Always save raw response for debugging
    date_str_now = datetime.now().strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    debug_path = OUTPUT_DIR / f"{date_str_now}_raw.txt"
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(raw_response)

    # Parse JSON
    json_text = extract_json_from_response(raw_response)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON parse failed ({e}) — attempting partial recovery...")
        data = recover_partial_json(json_text, categories)
        if not data:
            print(f"  [ERR] Recovery failed. Raw response saved to {debug_path.name}")
            return None, None
        print(f"  Partial recovery succeeded")

    # Validate
    is_valid, issues = validate_structure(data, categories)
    if not is_valid:
        print(f"  [WARN] Validation issues:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"  Validation passed — all {len(categories)} categories present")

    # Add metadata
    data["generated_at"] = datetime.now().isoformat()
    data["article_count"] = len(articles)

    # Save locally
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = save_categories(data, date_str)

    # Write to Supabase
    write_to_supabase(data, date_str)

    print("--- Category generation complete ---\n")
    return data, out_path


if __name__ == "__main__":
    """Run standalone using today's processed articles."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))

    today = datetime.now().strftime("%Y-%m-%d")
    all_path  = PROJECT_ROOT / "data" / "processed" / f"{today}_all.json"
    top_path  = PROJECT_ROOT / "data" / "processed" / f"{today}.json"

    # Prefer the full ranked pool; fall back to top-25 brief selection
    if all_path.exists():
        load_path = all_path
    elif top_path.exists():
        load_path = top_path
        print(f"  [WARN] Full pool not found — using top-25 brief selection only.")
        print(f"         Run fetch.py or main.py to generate the full article pool.")
    else:
        print(f"No processed articles found for {today}.")
        print("Run fetch.py first, or run main.py for the full pipeline.")
        sys.exit(1)

    with open(load_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    print(f"Loaded {len(articles)} articles from {load_path.name}")
    data, path = generate_categories(articles)

    if data:
        cats = data.get("categories", {})
        print(f"\n=== PREVIEW ({len(cats)} categories) ===")
        for cat_id, cat_data in list(cats.items())[:3]:
            stories = cat_data.get("stories", [])
            headline = (stories[0] or {}).get("headline", "N/A") if stories else "N/A"
            has_content = cat_data.get("has_content", True)
            story_count = len([s for s in stories if s])
            flag = f" [{story_count} stories]" if has_content else " [no coverage]"
            print(f"  {cat_id}: {headline[:70]}{flag}")
        if len(cats) > 3:
            print(f"  ... and {len(cats) - 3} more categories")
