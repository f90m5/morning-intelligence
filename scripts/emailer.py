"""
emailer.py — Send personalised daily brief emails to all signed-up users.

Pulls today's category data and each user's preferences from Supabase,
builds a custom HTML email respecting their category order/depth/toggles,
and sends via Brevo SMTP (smtp-relay.brevo.com).

Setup (one-time):
    1. Sign up at brevo.com, verify dailynews.it.com domain
    2. Go to SMTP & API → SMTP, generate an SMTP key
    3. Add to your .env:
         BREVO_SMTP_USER=your@login.email
         BREVO_SMTP_KEY=xsmtpsib-xxxx
    Also add both to GitHub Actions secrets.

Usage:
    from scripts.emailer import send_brief_emails
    send_brief_emails(date_str)          # called from main.py after category gen
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

SENDER_EMAIL   = "brief@dailynews.it.com"
SUBJECT_PREFIX = "Your Daily News"
APP_URL        = "https://dailynews.it.com/app/"

# Category metadata — must stay in sync with index.html
CATEGORIES = [
    {"id": "ai",            "label": "AI",            "color": "#7e9ee8"},
    {"id": "geopolitics",   "label": "Geopolitics",   "color": "#c97272"},
    {"id": "markets",       "label": "Markets",       "color": "#5aaa7c"},
    {"id": "technology",    "label": "Technology",    "color": "#6090c8"},
    {"id": "energy",        "label": "Energy",        "color": "#c49840"},
    {"id": "cybersecurity", "label": "Cybersecurity", "color": "#9272c8"},
    {"id": "startups",      "label": "Startups",      "color": "#7e8ec4"},
    {"id": "science",       "label": "Science",       "color": "#4aaab8"},
    {"id": "defense",       "label": "Defense",       "color": "#bc7840"},
    {"id": "business",      "label": "Business",      "color": "#48a890"},
    {"id": "climate",       "label": "Climate",       "color": "#62aa52"},
    {"id": "healthcare",    "label": "Healthcare",    "color": "#bc70b0"},
]
CAT_MAP       = {c["id"]: c for c in CATEGORIES}
DEFAULT_ORDER = [c["id"] for c in CATEGORIES]


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
    return create_client(url, key)


def _fetch_today_categories(sb, date_str):
    """Return dict of category_id → row for today."""
    rows = sb.table("daily_categories").select("*").eq("date", date_str).execute().data
    return {r["category"]: r for r in rows}


def _fetch_all_users(sb):
    """
    Return list of {id, email} for every confirmed Supabase Auth user.
    Requires the service key (bypasses RLS).
    """
    result = sb.auth.admin.list_users()
    users = []
    for user in result:
        if user.email and user.email_confirmed_at:
            users.append({"id": user.id, "email": user.email})
    return users


def _fetch_user_prefs(sb, user_id):
    """
    Return (ordered_cat_ids, prefs_dict) for a user.
    Falls back to defaults if no saved prefs.
    """
    rows = sb.table("user_settings").select("*").eq("user_id", user_id).execute().data

    prefs = {c: {"selected": True, "depth": 2} for c in DEFAULT_ORDER}

    if not rows:
        return DEFAULT_ORDER, prefs

    sorted_rows = sorted(rows, key=lambda r: r.get("order_index", 999))
    ordered_ids = [r["category"] for r in sorted_rows if r["category"] in CAT_MAP]
    for cid in DEFAULT_ORDER:
        if cid not in ordered_ids:
            ordered_ids.append(cid)

    for r in rows:
        cid = r["category"]
        if cid in CAT_MAP:
            prefs[cid] = {
                "selected": r.get("selected", True),
                "depth":    r.get("depth_level", 2),
            }

    return ordered_ids, prefs


# ── Email HTML builder ────────────────────────────────────────────────────────

def _story_html(story, color):
    headline = story.get("headline", "")
    bullets  = story.get("bullets",  [])
    sources  = story.get("sources",  [])

    src_str = " · ".join(
        s.get("name", s) if isinstance(s, dict) else s for s in sources
    )

    bullets_html = "".join(
        f'<li style="margin:5px 0;color:#9a9590;font-size:13px;line-height:1.65;">'
        f'<span style="color:#5a5550;margin-right:6px;">–</span>{b}</li>'
        for b in bullets
    )

    return (
        f'<div style="margin-bottom:16px;">'
        f'<div style="font-size:14.5px;font-weight:700;color:#edeae0;'
        f'line-height:1.5;margin-bottom:6px;">{headline}</div>'
        + (f'<ul style="list-style:none;margin:0;padding:0;">{bullets_html}</ul>' if bullets_html else "")
        + (f'<div style="margin-top:8px;font-size:11px;color:#5a5550;font-style:italic;">{src_str}</div>' if src_str else "")
        + '</div>'
    )


def _category_html(row, depth, color, label):
    stories_data = [row.get("depth_1"), row.get("depth_2"), row.get("depth_3")]
    stories = [s for s in stories_data[:depth] if s and isinstance(s, dict)]
    if not stories:
        return ""

    divider = (
        '<div style="text-align:center;color:#2a2825;font-size:11px;'
        'letter-spacing:4px;margin:14px 0;">· · ·</div>'
    )
    stories_html = divider.join(_story_html(s, color) for s in stories)

    return (
        f'<div style="background:#1c1a17;border:1px solid #2e2b26;'
        f'border-left:3px solid {color};border-radius:8px;margin-bottom:18px;overflow:hidden;">'
        f'<div style="padding:14px 18px 12px;border-bottom:1px solid #2e2b26;">'
        f'<span style="font-size:13px;font-weight:700;letter-spacing:.04em;'
        f'text-transform:uppercase;color:{color};">{label}</span></div>'
        f'<div style="padding:14px 18px 18px;">{stories_html}</div>'
        f'</div>'
    )


def build_email_html(date_str, cat_data, ordered_ids, prefs):
    """Build the full personalised HTML email for one user."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = d.strftime("%A, %B %-d, %Y")
    except Exception:
        date_display = date_str

    visible = [
        cid for cid in ordered_ids
        if prefs.get(cid, {}).get("selected", True)
        and cid in cat_data
        and cat_data[cid].get("has_content", True)
    ]

    cats_html = ""
    for cid in visible:
        cat   = CAT_MAP.get(cid, {})
        p     = prefs.get(cid, {})
        cats_html += _category_html(
            row   = cat_data[cid],
            depth = p.get("depth", 2),
            color = cat.get("color", "#888"),
            label = cat.get("label", cid),
        )

    n = len(visible)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#0d0c0a;font-family:-apple-system,Arial,sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:28px 16px 56px;">

    <!-- Header -->
    <div style="padding-bottom:18px;margin-bottom:26px;border-bottom:1px solid #2e2b26;">
      <div style="font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
                  color:#7a7367;margin-bottom:6px;">{date_display}</div>
      <div style="font-size:22px;font-weight:800;color:#edeae0;letter-spacing:-.02em;">
        Your Daily News
      </div>
      <div style="font-size:12px;color:#7a7367;margin-top:4px;">
        {n} topic{"s" if n != 1 else ""}
      </div>
    </div>

    <!-- Content -->
    {cats_html}

    <!-- Footer -->
    <div style="margin-top:32px;padding-top:16px;border-top:1px solid #2e2b26;
                font-size:11px;color:#4a4740;text-align:center;line-height:2;">
      <a href="{APP_URL}" style="color:#7a7367;text-decoration:none;">View full brief →</a>
      &nbsp;·&nbsp;
      Customize your feed in the web app
    </div>

  </div>
</body>
</html>"""


# ── Main send function ────────────────────────────────────────────────────────

def _send_via_brevo(smtp_user, smtp_key, to_email, subject, html_body):
    """Send a single email via Brevo SMTP. Raises on failure."""
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"Daily News <{SENDER_EMAIL}>"
    msg["To"]      = to_email
    msg["Subject"] = subject
    # List-Unsubscribe header — Gmail bulk sender requirement
    msg["List-Unsubscribe"] = f"<{APP_URL}settings>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp-relay.brevo.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_key)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())


def send_brief_emails(date_str=None):
    """
    Main entry point. Pull all users + prefs from Supabase,
    build a personalised email for each, and send via Brevo SMTP.
    """
    smtp_user = os.getenv("BREVO_SMTP_USER")
    smtp_key  = os.getenv("BREVO_SMTP_KEY")
    if not smtp_user or not smtp_key:
        print("  [SKIP] BREVO_SMTP_USER / BREVO_SMTP_KEY not set — skipping email.")
        return False

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        sb = _supabase_client()
    except RuntimeError as e:
        print(f"  [SKIP] {e}")
        return False

    print(f"\n--- Sending personalised emails for {date_str} ---")

    cat_data = _fetch_today_categories(sb, date_str)
    if not cat_data:
        print("  [SKIP] No category data for today.")
        return False

    try:
        users = _fetch_all_users(sb)
    except Exception as e:
        print(f"  [ERR] Could not fetch users: {e}")
        return False

    if not users:
        print("  [SKIP] No confirmed users found.")
        return False

    print(f"  {len(users)} confirmed user(s)")
    subject = f"{SUBJECT_PREFIX} — {date_str}"
    sent = 0

    for user in users:
        try:
            ordered_ids, prefs = _fetch_user_prefs(sb, user["id"])
            html = build_email_html(date_str, cat_data, ordered_ids, prefs)
            _send_via_brevo(smtp_user, smtp_key, user["email"], subject, html)
            print(f"  ✓ {user['email']}")
            sent += 1
        except Exception as e:
            print(f"  [ERR] {user['email']}: {e}")

    print(f"--- Email done: {sent}/{len(users)} sent ---\n")
    return sent > 0


# ── Legacy shim — main.py calls send_brief_email(markdown, date) ─────────────
def send_brief_email(markdown_text=None, date_str=None):
    """Backwards-compat wrapper. Ignores markdown_text, uses Supabase data."""
    return send_brief_emails(date_str)


if __name__ == "__main__":
    send_brief_emails(datetime.now().strftime("%Y-%m-%d"))
