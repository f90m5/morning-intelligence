"""
publish_html.py — Convert the daily brief markdown to a mobile-friendly HTML page
and optionally push to GitHub Pages.

Usage:
    from scripts.publish_html import publish_brief_html
    publish_brief_html(markdown_text)
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"  # GitHub Pages serves from /docs
WIDGET_DATA_PATH = DOCS_DIR / "widget.json"
TEMPLATE_DIR = PROJECT_ROOT / "scripts"


def get_html_template():
    """Return the full HTML template with %%DATE%%, %%DATE_LONG%%, %%CONTENT%% placeholders."""
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="color-scheme" content="dark">
<title>Daily Brief — %%DATE%%</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0b;
    --surface: #141416;
    --surface-hover: #1a1a1e;
    --border: #232328;
    --border-subtle: #1c1c20;
    --text: #f0f0f3;
    --text-secondary: #c0c0c8;
    --text-muted: #7a7a86;
    --accent: #6b8afd;
    --accent-soft: rgba(107,138,253,0.08);
    --green: #4ade80;
    --green-soft: rgba(74,222,128,0.08);
    --orange: #f59e0b;
    --orange-soft: rgba(245,158,11,0.08);
    --red: #f87171;
    --red-soft: rgba(248,113,113,0.08);
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    padding: 0;
    margin: 0;
  }

  .page {
    max-width: 640px;
    margin: 0 auto;
    padding: 0 20px 80px 20px;
  }

  /* ——— Header ——— */
  .header {
    padding: 48px 0 32px;
    margin-bottom: 32px;
  }

  .header-top {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .header-dot {
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
    flex-shrink: 0;
  }

  .header h1 {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-secondary);
  }

  .header .date {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.8px;
    color: var(--text);
    line-height: 1.2;
  }

  /* ——— Section Cards ——— */
  .section {
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    border-left: 2px solid var(--accent);
    border-radius: 8px;
    padding: 24px 24px 20px;
    margin-bottom: 14px;
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--accent);
    margin-bottom: 14px;
    display: inline-block;
  }

  .section-label.green { color: var(--green); }
  .section-label.orange { color: var(--orange); }
  .section-label.accent { color: var(--accent); }

  .section:has(.section-label.green) { border-left-color: var(--green); }
  .section:has(.section-label.orange) { border-left-color: var(--orange); }
  .section:has(.section-label.accent) { border-left-color: var(--accent); }

  /* ——— Typography ——— */
  h2 {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.3px;
    color: var(--text);
    margin-bottom: 16px;
    line-height: 1.3;
  }

  h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
    margin-top: 18px;
    margin-bottom: 6px;
  }

  p {
    font-size: 14.5px;
    color: var(--text-secondary);
    margin-bottom: 14px;
    line-height: 1.75;
  }

  /* ——— Lists ——— */
  ul, ol {
    padding-left: 0;
    margin-bottom: 4px;
    list-style: none;
  }

  li {
    font-size: 14.5px;
    margin-bottom: 0;
    padding: 14px 0 14px 16px;
    line-height: 1.7;
    color: var(--text-secondary);
    position: relative;
    border-bottom: 1px solid var(--border-subtle);
  }

  li:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  li:first-child {
    padding-top: 0;
  }

  li::before {
    content: '';
    position: absolute;
    left: 0;
    top: 24px;
    width: 4px;
    height: 4px;
    background: var(--text-muted);
    border-radius: 50%;
  }

  li:first-child::before {
    top: 10px;
  }

  /* Lead bold in a bullet — acts as a mini-headline */
  li > strong:first-child {
    color: var(--text);
    display: inline;
  }

  /* Subheading paragraphs after a list need breathing room */
  ul + p, ol + p {
    margin-top: 18px;
  }

  /* ——— Inline ——— */
  strong {
    font-weight: 600;
    color: var(--text);
  }

  em {
    color: var(--text-muted);
    font-style: italic;
  }

  code {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 2px 7px;
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12.5px;
    color: var(--accent);
  }

  pre {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    overflow-x: auto;
    margin: 14px 0;
    -webkit-overflow-scrolling: touch;
  }

  pre code {
    background: none;
    border: none;
    padding: 0;
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--text-secondary);
  }

  /* ——— Footer ——— */
  .footer {
    text-align: center;
    padding: 40px 0;
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.3px;
  }

  .footer-line {
    width: 32px;
    height: 1px;
    background: var(--border);
    margin: 0 auto 16px;
  }

  /* ——— Scrollbar ——— */
  pre::-webkit-scrollbar { height: 6px; }
  pre::-webkit-scrollbar-track { background: transparent; }
  pre::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* ——— Mobile tweaks ——— */
  @media (max-width: 480px) {
    .page { padding: 0 16px 60px 16px; }
    .header { padding: 36px 0 24px; }
    .header .date { font-size: 24px; }
    .section { padding: 20px 18px 16px; border-radius: 12px; }
  }

  /* ——— Highlighted figures ——— */
  .fig {
    color: var(--text);
    font-weight: 500;
  }

  /* Dark mode only — no light override */
</style>
</head>
<body>

<div class="page">

<div class="header">
  <div class="header-top">
    <div class="header-dot"></div>
    <h1>Daily Brief</h1>
  </div>
  <div class="date">%%DATE_LONG%%</div>
</div>

%%CONTENT%%

<div class="footer">
  <div class="footer-line"></div>
  Generated by Daily Brief
</div>

</div>
</body>
</html>"""


def markdown_to_html_sections(markdown_text):
    """
    Convert the brief's markdown into styled HTML sections.
    Splits on ## headings and wraps each in a card.
    """
    sections = re.split(r'^## ', markdown_text, flags=re.MULTILINE)
    html_parts = []

    section_meta = {
        "1": ("Headlines", "", ""),
        "2": ("Impact", "", ""),
        "3": ("Tech & Analytics", "green", ""),
        "4": ("Watch", "accent", ""),
        "5": ("Market Movers", "", ""),
        "6": ("Skill Tips", "orange", ""),
    }

    for section in sections:
        section = section.strip()
        if not section:
            continue
        if section.startswith("# "):
            continue

        num_match = re.match(r'^(\d+)\.?\s*(.*)', section)
        if num_match:
            num = num_match.group(1)
            meta = section_meta.get(num, ("", "", ""))
            label = meta[0]
            label_class = meta[1]
        else:
            label = ""
            label_class = ""

        html_content = convert_markdown_block(section)

        card = '<div class="section">\n'
        if label:
            cls = f' class="section-label {label_class}"' if label_class else ' class="section-label"'
            card += f'  <span{cls}>{label}</span>\n'
        card += f'  {html_content}\n'
        card += '</div>\n'
        html_parts.append(card)

    return "\n".join(html_parts)


def convert_markdown_block(text):
    """Convert a block of markdown to HTML."""
    lines = text.split("\n")
    html_lines = []
    in_list = False
    in_code_block = False
    code_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code_block:
                code_content = "\n".join(code_lines)
                html_lines.append(f"<pre><code>{code_content}</code></pre>")
                code_lines = []
                in_code_block = False
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(escaped(stripped))
            continue

        if not stripped:
            # Don't close list if the next non-empty line is also a bullet
            if in_list:
                next_is_bullet = False
                for future_line in lines[i+1:]:
                    fs = future_line.strip()
                    if not fs:
                        continue
                    for bp in ["- ", "* ", "• "]:
                        if fs.startswith(bp):
                            next_is_bullet = True
                            break
                    break
                if not next_is_bullet:
                    html_lines.append("</ul>")
                    in_list = False
            continue

        # Headings within sections
        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{inline_format(stripped[4:])}</h3>")
            continue

        # Section title (the ## heading line itself, first line)
        heading_match = re.match(r'^\d+\.?\s+(.+)', stripped)
        if i == 0 and heading_match:
            html_lines.append(f"<h2>{inline_format(heading_match.group(1))}</h2>")
            continue

        # Bullet points (-, *, •)
        bullet_content = None
        for bp in ["- ", "* ", "• "]:
            if stripped.startswith(bp):
                bullet_content = stripped[len(bp):]
                break
        if bullet_content is not None:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"  <li>{inline_format(bullet_content)}</li>")
            continue

        # Regular paragraph
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code_block:
        code_content = "\n".join(code_lines)
        html_lines.append(f"<pre><code>{code_content}</code></pre>")

    return "\n".join(html_lines)


def inline_format(text):
    """Apply inline markdown formatting and highlight key figures."""
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Highlight key figures: percentages, dollar amounts, large numbers
    # Skip anything already inside an HTML tag
    text = _highlight_figures(text)
    return text


def _highlight_figures(text):
    """Wrap key numbers/figures in <span class='fig'> for visual emphasis."""
    # We need to avoid wrapping things already inside HTML tags
    parts = re.split(r'(<[^>]+>)', text)
    result = []
    for part in parts:
        if part.startswith('<'):
            result.append(part)
        else:
            # Percentages: +16%, -1.3%, 2.8%
            part = re.sub(r'([+\-−]?\d[\d,]*\.?\d*%)', r"<span class='fig'>\1</span>", part)
            # Dollar amounts: $150/barrel, $2.5B, $500,000
            part = re.sub(r'(\$[\d,]+\.?\d*[BMKTbmkt]?\b)', r"<span class='fig'>\1</span>", part)
            # Ticker symbols in parens: (MRVL), (XOM), (TSLA)
            part = re.sub(r'\(([A-Z]{2,5})\)', r"(<span class='fig'>\1</span>)", part)
            result.append(part)
    return ''.join(result)


def escaped(text):
    """HTML-escape special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate_bullet(text, max_len=70):
    """Shorten a bullet to fit on a widget line."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # strip bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)       # strip italic
    text = re.sub(r'`([^`]+)`', r'\1', text)       # strip code
    if len(text) <= max_len:
        return text
    for sep in [", ", " — ", " - ", "; "]:
        idx = text.find(sep)
        if 0 < idx < max_len:
            return text[:idx]
    return text[:max_len - 3] + "..."


def _extract_section_bullets(lines, section_marker, max_bullets=5):
    """Pull bullet points from a markdown section."""
    bullets = []
    in_section = False
    # Match common bullet markers: -, *, •
    bullet_prefixes = ["- ", "* ", "• "]
    for line in lines:
        if section_marker in line:
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section:
            stripped = line.strip()
            for prefix in bullet_prefixes:
                if stripped.startswith(prefix):
                    bullets.append(_truncate_bullet(stripped[len(prefix):]))
                    break
            if len(bullets) >= max_bullets:
                break
    return bullets


def _extract_section_text(lines, section_marker, max_len=200):
    """Pull paragraph text from a markdown section."""
    text = ""
    in_section = False
    for line in lines:
        if section_marker in line:
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section and line.strip() and not line.strip().startswith("#"):
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line.strip())
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            text += clean + " "
    text = text.strip()
    if len(text) > max_len:
        cut = text[:max_len].rfind(". ")
        if cut > 80:
            text = text[:cut + 1]
        else:
            text = text[:max_len - 3] + "..."
    return text


def extract_widget_data(markdown_text):
    """
    Pull out structured data for the iPhone widget.
    Widget is a preview of the full brief — same sections, condensed.
    """
    lines = markdown_text.strip().split("\n")

    # Date
    date = datetime.now().strftime("%B %d, %Y")
    for line in lines:
        date_match = re.search(r'Brief\s*[-—]\s*(.+)', line)
        if date_match:
            date = date_match.group(1).strip()
            break

    # Top stories — first 3 bullet points from section 1
    top_stories = _extract_section_bullets(lines, "## 1.", max_bullets=3)

    # Stock & Market Movers — from section 5
    stock_news = _extract_section_bullets(lines, "## 5.", max_bullets=3)

    # One Thing to Watch — section 4
    watch = _extract_section_text(lines, "## 4.", max_len=180)

    return {
        "date": date,
        "top_stories": top_stories,
        "stock_news": stock_news,
        "watch": watch,
        "updated": datetime.now().isoformat(),
    }


def publish_brief_html(markdown_text, push_to_git=False):
    """
    Main entry point. Converts brief to HTML and saves to docs/ for GitHub Pages.
    """
    print("\n--- Publishing HTML ---")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    date_short = today.strftime("%Y-%m-%d")
    date_long = today.strftime("%A, %B %d, %Y")

    # 1. Convert markdown to HTML sections
    content = markdown_to_html_sections(markdown_text)

    # 2. Build full HTML page using safe placeholders
    html = get_html_template()
    html = html.replace("%%DATE%%", date_short)
    html = html.replace("%%DATE_LONG%%", date_long)
    html = html.replace("%%CONTENT%%", content)

    # 3. Save as index.html (current brief) and dated archive
    index_path = DOCS_DIR / "index.html"
    archive_path = DOCS_DIR / f"{date_short}.html"

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  HTML saved: index.html + {date_short}.html")

    # 4. Generate widget data JSON
    widget_data = extract_widget_data(markdown_text)
    with open(WIDGET_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(widget_data, f, indent=2, ensure_ascii=False)

    print(f"  Widget data saved: widget.json")

    # 5. Push to GitHub if requested
    if push_to_git:
        push_to_github()

    print("--- HTML published ---\n")
    return index_path


def push_to_github():
    """Commit and push docs/ to GitHub for GitHub Pages."""
    try:
        subprocess.run(
            ["git", "add", "docs/"],
            cwd=PROJECT_ROOT, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Update brief: {datetime.now().strftime('%Y-%m-%d')}"],
            cwd=PROJECT_ROOT, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push"],
            cwd=PROJECT_ROOT, check=True, capture_output=True
        )
        print("  Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] Git push failed: {e.stderr.decode()[:200]}")
    except FileNotFoundError:
        print("  [WARN] Git not found. Skipping push.")


if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    brief_path = PROJECT_ROOT / "outputs" / "briefs" / f"{today}.md"

    if brief_path.exists():
        with open(brief_path, "r", encoding="utf-8") as f:
            markdown = f.read()
        publish_brief_html(markdown)
    else:
        print(f"No brief found for {today}. Run main.py first.")
