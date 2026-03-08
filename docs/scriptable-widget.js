// Daily Brief — Scriptable Widget
const BRIEF_URL = "https://f90m5.github.io/morning-intelligence";
const WIDGET_JSON = BRIEF_URL + "/widget.json";
const FULL_PAGE = BRIEF_URL + "/index.html";

async function createWidget() {
  let data;
  try {
    let req = new Request(WIDGET_JSON);
    data = await req.loadJSON();
  } catch (e) {
    return createErrorWidget("Could not load brief");
  }

  let w = new ListWidget();
  w.backgroundColor = new Color("#0d1117");
  w.url = FULL_PAGE;
  w.setPadding(12, 14, 12, 14);

  // ---- Header ----
  let headerStack = w.addStack();
  headerStack.layoutHorizontally();
  headerStack.centerAlignContent();

  let header = headerStack.addText("DAILY BRIEF");
  header.font = Font.boldSystemFont(10);
  header.textColor = new Color("#58a6ff");

  headerStack.addSpacer();

  let dateText = headerStack.addText(data.date || "Today");
  dateText.font = Font.regularSystemFont(10);
  dateText.textColor = new Color("#484f58");

  w.addSpacer(8);

  // ---- TOP STORIES ----
  let topLabel = w.addText("TOP STORIES");
  topLabel.font = Font.boldSystemFont(9);
  topLabel.textColor = new Color("#58a6ff");
  w.addSpacer(4);

  let stories = data.top_stories || [];
  for (let i = 0; i < stories.length; i++) {
    let row = w.addStack();
    row.layoutHorizontally();
    row.topAlignContent();
    row.spacing = 6;

    let dot = row.addText("▸");
    dot.font = Font.mediumSystemFont(11);
    dot.textColor = new Color("#58a6ff");
    dot.size = new Size(10, 18);

    let text = row.addText(stories[i]);
    text.font = Font.mediumSystemFont(12);
    text.textColor = new Color("#e6edf3");
    text.lineLimit = 2;

    w.addSpacer(3);
  }

  w.addSpacer(6);

  // ---- STOCK & MARKET NEWS ----
  let stockNews = data.stock_news || [];
  if (stockNews.length > 0) {
    let stockLabel = w.addText("IMPACT & OUTLOOK");
    stockLabel.font = Font.boldSystemFont(9);
    stockLabel.textColor = new Color("#d29922");
    w.addSpacer(4);

    for (let i = 0; i < stockNews.length; i++) {
      let row = w.addStack();
      row.layoutHorizontally();
      row.topAlignContent();
      row.spacing = 6;

      let dot = row.addText("▸");
      dot.font = Font.mediumSystemFont(11);
      dot.textColor = new Color("#d29922");
      dot.size = new Size(10, 18);

      let text = row.addText(stockNews[i]);
      text.font = Font.mediumSystemFont(12);
      text.textColor = new Color("#e6edf3");
      text.lineLimit = 2;

      w.addSpacer(3);
    }

    w.addSpacer(6);
  }

  // ---- WATCH TODAY ----
  let watch = data.watch || "";
  if (watch) {
    let sep = w.addStack();
    sep.size = new Size(0, 1);
    sep.backgroundColor = new Color("#21262d");
    w.addSpacer(6);

    let watchLabel = w.addText("WATCH TODAY");
    watchLabel.font = Font.boldSystemFont(9);
    watchLabel.textColor = new Color("#3fb950");
    w.addSpacer(3);

    let watchText = w.addText(watch);
    watchText.font = Font.regularSystemFont(11);
    watchText.textColor = new Color("#c9d1d9");
    watchText.lineLimit = 4;
    watchText.minimumScaleFactor = 0.85;
  }

  w.addSpacer(null);

  // ---- Footer ----
  let footer = w.addText("Tap for full brief →");
  footer.font = Font.regularSystemFont(9);
  footer.textColor = new Color("#484f58");
  footer.rightAlignText();

  return w;
}

function createErrorWidget(message) {
  let w = new ListWidget();
  w.backgroundColor = new Color("#0d1117");
  w.url = FULL_PAGE;
  let text = w.addText(message);
  text.font = Font.regularSystemFont(14);
  text.textColor = new Color("#f85149");
  text.centerAlignText();
  return w;
}

let widget = await createWidget();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentLarge();
}
Script.complete();
