"""
generate_brief.py — Send ranked articles to Claude and generate the daily brief.

Quality is controlled via config/quality.json:
  - "fast"    : Sonnet, 2000 tokens, no verification  (~$0.05, ~30s)
  - "standard": Sonnet, 4000 tokens, one verify pass   (~$0.15, ~60s)
  - "deep"    : Opus, 6000 tokens, one verify pass      (~$1.00, ~90s)

Usage:
    from scripts.generate_brief import generate_brief
    markdown = generate_brief(articles)
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "prompts" / "brief_prompt.txt"
VERIFY_PROMPT_PATH = PROJECT_ROOT / "prompts" / "verify_prompt.txt"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "briefs"
QUALITY_CONFIG_PATH = PROJECT_ROOT / "config" / "quality.json"

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Quality presets
QUALITY_PRESETS = {
    "fast": {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "verify": False,
        "verify_model": None,
    },
    "standard": {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4000,
        "verify": True,
        "verify_model": "claude-sonnet-4-20250514",
    },
    "deep": {
        "model": "claude-opus-4-20250514",
        "max_tokens": 6000,
        "verify": True,
        "verify_model": "claude-opus-4-20250514",
    },
}


def load_quality_config():
    """Load quality settings. Falls back to 'standard' if no config."""
    if QUALITY_CONFIG_PATH.exists():
        with open(QUALITY_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        preset_name = config.get("preset", "standard")
    else:
        preset_name = "standard"

    if preset_name in QUALITY_PRESETS:
        preset = QUALITY_PRESETS[preset_name]
        print(f"  Quality preset: {preset_name} (model={preset['model']}, verify={preset['verify']})")
        return preset
    else:
        print(f"  [WARN] Unknown preset '{preset_name}', using standard")
        return QUALITY_PRESETS["standard"]


def load_prompt_template():
    """Load the prompt template from file."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def format_articles_for_prompt(articles):
    """
    Format article list into a readable string for the prompt.
    Only sends what Claude needs: title, source, category, description.
    """
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


def build_prompt(articles):
    """Build the full prompt by inserting articles into the template."""
    from scripts.history import get_recent_context

    template = load_prompt_template()
    today = datetime.now().strftime("%B %d, %Y")
    articles_text = format_articles_for_prompt(articles)

    prompt = template.replace("{date}", today).replace("{articles}", articles_text)

    # Inject recent brief context so Claude knows what was already covered
    recent_context = get_recent_context(max_days=3)
    if recent_context:
        prompt = recent_context + "\n\n---\n\n" + prompt
        print(f"  Injected {len(recent_context)} chars of recent context")

    return prompt


def call_claude(prompt, model, max_tokens, max_retries=2):
    """
    Call the Claude API with the prompt.
    Returns the response text, or None on failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [ERR] ANTHROPIC_API_KEY not found in .env")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(max_retries):
        try:
            print(f"  Calling {model} (attempt {attempt + 1}, max_tokens={max_tokens})...")
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            text = response.content[0].text

            # Log token usage
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


def verify_brief(draft, verify_model, max_tokens):
    """
    Run a verification pass on the draft brief.
    Returns a refined version with corrections.
    """
    print("\n  --- Verification pass ---")

    verify_prompt = f"""You are a fact-checking editor reviewing a daily news brief. Your job is to improve it, not rewrite it.

Here is the draft brief:

{draft}

Review the brief and produce a corrected final version. Apply these checks:

1. SOURCING: Every factual claim should attribute a source (e.g., "according to...", "per...", "reported by..."). If a bullet makes a claim without attribution, add a reasonable source based on which outlet would report that type of story.

2. SPECIFICITY: Every bullet should include dates (when), numbers (how much), and names (who/what). If a bullet is vague like "oil prices surged", make it specific like "Brent crude rose 8% to $148/barrel on March 6".

3. ACCURACY: Flag anything that seems internally inconsistent or implausible. If two bullets contradict each other, resolve the contradiction.

4. COMPLETENESS: Does each section cover what it should? Are the skill tips practical enough to actually use? Does "One Thing to Watch" have a timeframe?

5. CONCISENESS: Cut any filler phrases ("it's worth noting that", "interestingly", "it should be noted"). Every word should earn its place.

Output the complete corrected brief in the same markdown format. If everything is already good, return it unchanged. Do not add commentary — just output the final brief."""

    refined = call_claude(verify_prompt, verify_model, max_tokens)

    if refined:
        # Strip any preamble the model might add before the markdown
        if "# Daily Brief" in refined:
            refined = refined[refined.index("# Daily Brief"):]
        print("  --- Verification complete ---")
        return refined
    else:
        print("  [WARN] Verification failed, using original draft")
        return draft


def save_brief(markdown, date_str=None):
    """Save the generated brief as a markdown file."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{date_str}.md"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"  Brief saved to {out_path.name}")
    return out_path


def generate_brief(articles):
    """
    Main entry point. Takes ranked articles, generates the brief via Claude.
    Quality level is controlled by config/quality.json.
    Returns (markdown_string, file_path) or (None, None) on failure.
    """
    print("\n--- Generating brief ---")

    if not articles:
        print("  [ERR] No articles provided")
        return None, None

    # Load quality settings
    quality = load_quality_config()

    # 1. Build the prompt
    prompt = build_prompt(articles)
    print(f"  Prompt built ({len(prompt)} chars, {len(articles)} articles)")

    # 2. Generate draft
    draft = call_claude(prompt, quality["model"], quality["max_tokens"])
    if not draft:
        print("  [ERR] Failed to generate brief")
        return None, None

    # 3. Verification pass (if enabled)
    if quality["verify"]:
        markdown = verify_brief(draft, quality["verify_model"], quality["max_tokens"])
    else:
        markdown = draft

    # 4. Save
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = save_brief(markdown, date_str)

    print("--- Brief generated ---\n")
    return markdown, out_path


# Allow running standalone with today's processed articles
if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    processed_path = PROJECT_ROOT / "data" / "processed" / f"{today}.json"

    if not processed_path.exists():
        print(f"No processed articles found for {today}.")
        print("Run fetch.py first.")
    else:
        with open(processed_path, "r", encoding="utf-8") as f:
            articles = json.load(f)

        markdown, path = generate_brief(articles)
        if markdown:
            print("=== BRIEF PREVIEW (first 500 chars) ===")
            print(markdown[:500])
            print("...")
