# Morning Intelligence Brief

A personal automated daily briefing system that combines real news with structured learning concepts in business analytics, data science, and tech.

## Setup

1. **Create a virtual environment:**
   ```
   cd morning-intelligence
   python -m venv venv
   venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```

2. **Add your API keys:**
   - Copy `.env.example` to `.env`
   - Add your Anthropic API key (required): https://console.anthropic.com/
   - Optionally add a NewsAPI key: https://newsapi.org/

3. **Run it:**
   ```
   python scripts/main.py
   ```

Your daily brief will be saved to `outputs/briefs/YYYY-MM-DD.md`.

## Project Structure

```
config/         — RSS feed URLs and categories
data/           — raw and processed article data
scripts/        — fetch.py, generate_brief.py, main.py
prompts/        — Claude prompt template
outputs/briefs/ — generated daily briefs
```
