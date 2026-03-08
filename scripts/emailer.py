"""
emailer.py — Send the daily brief via email to configured recipients.

Uses Gmail SMTP with an App Password (not your regular password).
Recipients are stored in config/email_recipients.json for easy editing.

Setup (one-time):
    1. Go to https://myaccount.google.com/apppasswords
    2. Generate an App Password for "Mail" → "Windows Computer"
    3. Add to your .env file:  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

Usage:
    from scripts.emailer import send_brief_email
    send_brief_email(markdown_text, "2026-03-08")
"""

import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMAIL_CONFIG_PATH = PROJECT_ROOT / "config" / "email_recipients.json"

load_dotenv(PROJECT_ROOT / ".env", override=True)


def load_email_config():
    """Load recipient list and settings from config file."""
    with open(EMAIL_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def markdown_to_plain(md):
    """Convert markdown to readable plain text for the email body."""
    text = md
    # Bold **text** → text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Italic *text* → text
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Code `text` → text
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Section headers: ## 1. Title → === Title ===
    text = re.sub(r'^## \d+\.?\s*(.+)$', r'\n=== \1 ===', text, flags=re.MULTILINE)
    # Main header
    text = re.sub(r'^# (.+)$', r'\1\n' + '=' * 40, text, flags=re.MULTILINE)
    return text.strip()


def markdown_to_email_html(md):
    """Convert brief markdown to a simple styled HTML email."""
    lines = md.strip().split("\n")
    html_parts = ['<div style="font-family: -apple-system, Arial, sans-serif; max-width: 640px; margin: 0 auto; color: #222; line-height: 1.7; font-size: 15px;">']

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        # Main title
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:]
            html_parts.append(f'<h1 style="font-size: 22px; border-bottom: 2px solid #333; padding-bottom: 8px; margin-top: 24px;">{title}</h1>')
            continue

        # Section headers
        h2_match = re.match(r'^## \d+\.?\s*(.+)', stripped)
        if h2_match:
            heading = h2_match.group(1)
            html_parts.append(f'<h2 style="font-size: 17px; color: #1a56db; margin-top: 28px; margin-bottom: 8px;">{heading}</h2>')
            continue

        # Sub-headings (### or bold standalone)
        if stripped.startswith("### "):
            html_parts.append(f'<h3 style="font-size: 15px; margin-top: 16px; margin-bottom: 4px;">{stripped[4:]}</h3>')
            continue

        # Bold standalone line (subheading in Top Stories)
        bold_match = re.match(r'^\*\*(.+?)\*\*$', stripped)
        if bold_match:
            html_parts.append(f'<p style="font-weight: 700; margin-top: 16px; margin-bottom: 4px;">{bold_match.group(1)}</p>')
            continue

        # Bullet points
        bullet_content = None
        for bp in ["- ", "* ", "• "]:
            if stripped.startswith(bp):
                bullet_content = stripped[len(bp):]
                break
        if bullet_content is not None:
            # Inline formatting
            bullet_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', bullet_content)
            bullet_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', bullet_content)
            bullet_content = re.sub(r'`([^`]+)`', r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:13px;">\1</code>', bullet_content)
            html_parts.append(f'<p style="margin: 8px 0 8px 16px; padding-left: 12px; border-left: 2px solid #ddd;">&#8226; {bullet_content}</p>')
            continue

        # Regular paragraph
        para = stripped
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
        para = re.sub(r'\*(.+?)\*', r'<em>\1</em>', para)
        para = re.sub(r'`([^`]+)`', r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:13px;">\1</code>', para)
        html_parts.append(f'<p style="margin: 8px 0;">{para}</p>')

    html_parts.append('</div>')
    return "\n".join(html_parts)


def send_brief_email(markdown_text, date_str=None):
    """
    Send the brief to all configured recipients via Gmail SMTP.
    Requires GMAIL_APP_PASSWORD in .env.
    """
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not app_password:
        print("  [SKIP] GMAIL_APP_PASSWORD not set in .env — skipping email.")
        print("  To enable email: https://myaccount.google.com/apppasswords")
        return False

    config = load_email_config()
    sender = config["sender_email"]
    recipients = config["recipients"]
    prefix = config.get("subject_prefix", "Daily Brief")

    if not recipients:
        print("  [SKIP] No recipients in config/email_recipients.json")
        return False

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    subject = f"{prefix} — {date_str}"

    # Build multipart email (HTML + plain text fallback)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    plain_body = markdown_to_plain(markdown_text)
    html_body = markdown_to_email_html(markdown_text)

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"  Email sent to {len(recipients)} recipients: {', '.join(recipients)}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("  [ERR] Gmail auth failed. Check GMAIL_APP_PASSWORD in .env")
        print("  Generate one at: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"  [ERR] Email send failed: {e}")
        return False


if __name__ == "__main__":
    """Test: send today's brief via email."""
    today = datetime.now().strftime("%Y-%m-%d")
    brief_path = PROJECT_ROOT / "outputs" / "briefs" / f"{today}.md"

    if brief_path.exists():
        with open(brief_path, "r", encoding="utf-8") as f:
            markdown = f.read()
        send_brief_email(markdown, today)
    else:
        print(f"No brief found for {today}. Run main.py first.")
