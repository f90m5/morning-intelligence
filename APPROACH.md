# Approach & Priorities — Daily Brief

## What This Project Is
A personal automated daily briefing system that delivers real, sourced, specific news — not generic AI summaries. The goal is an 8-10 minute read every morning that makes me feel informed enough to cite what I read without further research.

## Name
**Daily Brief** — not "Morning Intelligence Brief." Keep it simple.

## Core Philosophy
- **Specificity over generality.** Every bullet should include dates, numbers, named sources, and enough context to cite. "The economy is slowing" is useless. "February jobs report showed a loss of 92,000 positions, per BLS data released March 6" is what I want.
- **Signal over noise.** Skip celebrity news, clickbait, minor product updates. Focus on things that matter for someone in analytics/business.
- **Sourced everything.** Every factual claim references who reported it or where the data comes from. "According to..." / "per..." / "reported by..." should appear constantly.
- **Sharp tone.** Like a Bloomberg terminal note, not a blog post. Direct, analytical, concise.
- **Practical, not theoretical.** The skill tips should be things I can actually try today, not abstract advice.

## Section Order (Important)
1. **Top Stories** — the headlines, 4-5 sourced bullets
2. **Impact and What to Watch For** — so what? what does it mean?
3. **Tech, Analytics & IS News** — my field, always include this
4. **One Thing to Watch** — a developing story to track over days/weeks
5. **Stock & Market Movers** — tickers, percentages, catalysts (will eventually connect to my portfolio)
6. **Tools & Skill Tips** — two practical tips, one can connect to today's news

## Delivery
- Full brief: GitHub Pages HTML (dark theme, mobile-friendly)
- Widget: Scriptable large widget on iPhone home screen showing preview (top stories + stock news + watch)
- Tap widget → opens full brief in browser

## Quality Control
- I want the option to control depth: fast/standard/deep presets
- Standard preset includes a verification pass where the AI checks its own work for sourcing, specificity, accuracy
- The verification pass matters — it catches lazy generalizations

## What I Don't Want
- Generic AI summaries with no sources
- Vague bullets like "markets were mixed" or "tech stocks moved"
- Emojis in the brief
- Overly long output — keep it focused
- Clickbait or filler content

## Future Direction
- **Portfolio integration**: Link my actual stock holdings so section 5 gives me personalized news on what I own
- **Task Scheduler**: Automate to run every morning on my PC
- **Memory system**: The brief should learn over time what I care about
- **This is my first deployable AI agent project** — I'm learning as I go, so keep explanations clear and don't skip steps

## How I Work
- I run this on my personal Windows PC in a controlled environment
- Project lives at: `C:\Users\Donovan\Desktop\Claude Work\Daily brief\morning-intelligence`
- I use a Python venv and activate it manually
- I push to GitHub myself from the command line
- I want to understand what's happening, not just have it done for me
