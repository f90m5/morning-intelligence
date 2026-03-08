# Technical Notes — Daily Brief

## Project Structure

```
morning-intelligence/
├── config/
│   ├── sources.json        # 27 RSS feeds across 6 categories
│   └── quality.json        # Controls generation quality preset
├── prompts/
│   └── brief_prompt.txt    # Claude API prompt template (6 sections)
├── scripts/
│   ├── fetch.py            # RSS fetching, dedup, category-balanced selection
│   ├── generate_brief.py   # Claude API calls + optional verification pass
│   ├── publish_html.py     # Markdown → HTML + widget.json extraction
│   └── main.py             # Orchestrator: fetch → generate → publish
├── docs/
│   ├── index.html          # GitHub Pages output (auto-generated)
│   ├── widget.json         # Widget data (auto-generated)
│   └── scriptable-widget.js # Scriptable iOS widget code
├── outputs/
│   ├── briefs/             # Dated markdown outputs
│   └── run.log             # Execution log
├── .env                    # ANTHROPIC_API_KEY (not committed)
├── .gitignore
├── requirements.txt        # feedparser, anthropic, python-dotenv, requests
└── README.md
```

## Key Technical Details

### RSS Feeds (config/sources.json)
- 27 feeds across 6 categories: business, markets, technology, ai_data, world, science
- Each feed has a tier rating (1-3) used for ranking
- All feeds were live-tested on 2026-03-07
- Replaced broken feeds: AP News (403 error) → NPR Business, Reuters sample → MarketWatch

### Article Fetching (scripts/fetch.py)
- Filters to articles from last 48 hours
- Deduplicates by URL and fuzzy headline matching (difflib.SequenceMatcher, threshold 0.7)
- Ranks by: tier score + has description + has keywords
- Category-balanced selection: guarantees 2+ articles per category before filling remaining slots
- Default: selects top 20 articles

### Brief Generation (scripts/generate_brief.py)
- Quality presets defined in code:
  - **fast**: Sonnet, 2000 tokens, no verify (~$0.05)
  - **standard**: Sonnet, 4000 tokens, verify pass (~$0.15)
  - **deep**: Opus, 6000 tokens, Opus verify (~$1.00)
- Current preset controlled by `config/quality.json` → `{"preset": "standard"}`
- Verification pass: second API call checks sourcing, specificity, accuracy, completeness, conciseness
- Uses `override=True` in `load_dotenv()` (required for reliable .env loading)

### HTML Publishing (scripts/publish_html.py)
- Template uses `%%PLACEHOLDER%%` markers (not Python format strings) to avoid CSS brace conflicts
- Section meta mapping (numbered sections → display labels + colors):
  - 1: Headlines (default)
  - 2: Impact (default)
  - 3: Tech & Analytics (green)
  - 4: Watch (accent)
  - 5: Market Movers (default)
  - 6: Skill Tips (orange)
- Widget data extraction pulls from markdown sections:
  - top_stories: section 1, 3 bullets
  - stock_news: section 5, 3 bullets
  - watch: section 4 text
- Bullet parsing handles `- `, `* `, `• ` prefixes
- Dark theme default with light mode via `@media (prefers-color-scheme: light)`
- Saves: index.html + dated archive + widget.json, optional git push

### Scriptable Widget (docs/scriptable-widget.js)
- Fetches widget.json from GitHub Pages
- Layout: DAILY BRIEF header → TOP STORIES (3 blue bullets) → IMPACT & OUTLOOK (2 orange bullets) → WATCH TODAY (green text)
- Tap opens full brief at https://f90m5.github.io/morning-intelligence/index.html
- Uses `Font.mediumSystemFont` (not semiBold — that doesn't exist in Scriptable)

### Brief Sections (prompts/brief_prompt.txt)
1. Top Stories — 4-5 sourced bullets with dates, numbers, named sources
2. Impact and What to Watch For — 2-3 bullets on implications
3. Tech, Analytics & IS News — 2-3 bullets on tech/data topics
4. One Thing to Watch — developing story or trend with timeframe
5. Stock & Market Movers — 2-4 bullets with tickers, % moves, sources, catalysts
6. Tools & Skill Tips — two practical tips with short headings

Target length: 800-1100 words.

### 7-Day History System (scripts/history.py)
- Stores rolling 7-day history in `data/history.json`
- Auto-prunes entries older than 7 days on each save
- Each day's entry has: headlines (concise labels), topics (keywords), summary (one-liner)
- **Fetch integration**: `rank_articles()` applies a -4 score penalty to articles whose headlines are >65% similar to recent days (via `is_headline_stale()`)
- **Prompt integration**: `build_prompt()` injects a "RECENT BRIEFS" context block (last 3 days) at the top of the prompt, instructing Claude to not repeat stories unless there's a meaningful new development
- **Orchestrator**: `main.py` calls `save_today()` after each successful run to log what was covered
- History is seeded from existing briefs — running `save_today(markdown)` on any past brief populates it

## GitHub
- Repo: https://github.com/f90m5/morning-intelligence.git
- GitHub Pages: https://f90m5.github.io/morning-intelligence/
- Pages serves from `/docs` on main branch
- Git config: user.email = donovanquinn22@gmail.com, user.name = Donovan
- Safe directory added for: `C:/Users/Donovan/Desktop/Claude Work/Daily brief/morning-intelligence`

## Bugs Fixed (Reference)
| Issue | Root Cause | Fix |
|-------|-----------|-----|
| CSS `{{` in HTML output | Python f-string escaping written literally | Switched to `%%PLACEHOLDER%%` markers |
| .env not loading | Em dash chars in comments + missing override | Cleaned to ASCII, added `override=True` |
| Scriptable Font error | `Font.semiBoldSystemFont` doesn't exist | Changed to `Font.mediumSystemFont` |
| AP/Reuters 0 articles | AP 403, Reuters was sample file | Replaced with NPR Business, MarketWatch |
| Bullets not parsed | Claude outputs `•` sometimes | Added `•` to bullet prefix list |
| Git dubious ownership | VM-created files had different owner | Added safe.directory config |
| Category imbalance | Top-20 was 11 business, 0 science | Added `select_balanced()` with per-category minimums |

## Environment
- Python venv at `venv/` — activate with `venv\Scripts\activate` before running
- Windows PC, run from: `C:\Users\Donovan\Desktop\Claude Work\Daily brief\morning-intelligence`
- Entry point: `python scripts/main.py`

## Future Plans
- Windows Task Scheduler for daily automation
- Portfolio integration (config/portfolio.json) for personalized stock news in section 5
- Memory system (v2) for progressive learning
