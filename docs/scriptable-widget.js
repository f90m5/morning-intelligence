// Daily News — Scriptable Widget
// Paste this into Scriptable on your iPhone.
// Set widget size to Medium or Large for best results.

const WIDGET_JSON = "https://f90m5.github.io/morning-intelligence/widget.json";
const FULL_PAGE   = "https://f90m5.github.io/morning-intelligence/app/";

// How many stories to show per widget size
const MAX_STORIES = config.widgetFamily === "small"  ? 3
                  : config.widgetFamily === "medium" ? 5
                  : 8; // large

// ── Fetch data ──────────────────────────────────────────────────────────────
async function loadData() {
  try {
    const req = new Request(WIDGET_JSON);
    req.timeoutInterval = 10;
    return await req.loadJSON();
  } catch (e) {
    return null;
  }
}

// ── Widget builder ───────────────────────────────────────────────────────────
async function buildWidget(data) {
  const w = new ListWidget();
  w.backgroundColor = new Color("#131210");
  w.url = FULL_PAGE;
  w.setPadding(14, 16, 14, 16);

  if (!data || !data.stories || data.stories.length === 0) {
    const msg = w.addText("No brief available yet.");
    msg.font = Font.regularSystemFont(13);
    msg.textColor = new Color("#888888");
    msg.centerAlignText();
    return w;
  }

  // ── Date only — no branding ─────────────────────────────────────────────────
  const dateStr = (data.date || "").toUpperCase();
  const dateEl = w.addText(dateStr);
  dateEl.font = Font.regularSystemFont(9);
  dateEl.textColor = new Color("#555550");

  w.addSpacer(10);

  // ── Stories ─────────────────────────────────────────────────────────────────
  const stories = data.stories.slice(0, MAX_STORIES);

  for (let i = 0; i < stories.length; i++) {
    const s = stories[i];
    const color = new Color(s.color || "#888888");

    const row = w.addStack();
    row.layoutHorizontally();
    row.topAlignContent();
    row.spacing = 8;

    // Colored category pill
    const pill = row.addStack();
    pill.layoutHorizontally();
    pill.centerAlignContent();
    pill.setPadding(2, 5, 2, 5);
    pill.cornerRadius = 3;
    pill.backgroundColor = new Color(s.color || "#888888", 0.18);
    pill.size = new Size(config.widgetFamily === "small" ? 52 : 62, 16);

    const catLabel = pill.addText((s.category_label || s.category_id || "").toUpperCase());
    catLabel.font = Font.boldSystemFont(7);
    catLabel.textColor = color;
    catLabel.lineLimit = 1;
    catLabel.minimumScaleFactor = 0.7;

    // Headline text
    const textCol = row.addStack();
    textCol.layoutVertically();

    const headline = textCol.addText(s.headline || "");
    headline.font = Font.mediumSystemFont(12);
    headline.textColor = new Color("#e8e4dc");
    headline.lineLimit = 2;

    // Show teaser on large widget only
    if (config.widgetFamily === "large" && s.teaser) {
      const teaser = textCol.addText(s.teaser);
      teaser.font = Font.regularSystemFont(10);
      teaser.textColor = new Color("#7a7570");
      teaser.lineLimit = 1;
    }

    // Add spacing between stories, but not after the last one
    if (i < stories.length - 1) {
      w.addSpacer(config.widgetFamily === "small" ? 6 : 9);
    }
  }

  w.addSpacer(null); // push footer to bottom

  // ── Footer ──────────────────────────────────────────────────────────────────
  const footer = w.addText("Tap for full brief →");
  footer.font = Font.regularSystemFont(8);
  footer.textColor = new Color("#3a3830");
  footer.rightAlignText();

  return w;
}

// ── Run ──────────────────────────────────────────────────────────────────────
const data = await loadData();
const widget = await buildWidget(data);

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  // Preview in app — match the size you plan to use
  await widget.presentLarge();
}
Script.complete();
