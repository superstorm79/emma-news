#!/usr/bin/env python3
"""
החדשות של אמה — Daily Digest Generator
Step 1: Haiku + web search → plain text news summary
Step 2: (wait 90s) Haiku + tool_use → structured digest, zero JSON errors
"""

import os
import json
import time
import datetime
import anthropic
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OUTPUT_DIR  = Path("docs")
CONFIG_FILE = Path("docs/config.json")
MODEL       = "claude-haiku-4-5-20251001"

DEFAULT_SECTIONS = [
    {"id": "israel",  "icon": "🇮🇱", "label": "קרוב לבית",     "enabled": True},
    {"id": "world",   "icon": "🌍",  "label": "מבט על העולם",   "enabled": True},
    {"id": "science", "icon": "🔬",  "label": "גילוי היום",      "enabled": True},
    {"id": "tech",    "icon": "💡",  "label": "זרקור טכנולוגי", "enabled": True},
    {"id": "culture", "icon": "🎨",  "label": "פינת תרבות",     "enabled": True},
]

SECTION_COLORS = {
    "israel": "#e8f4f0", "world": "#e8f4e8", "science": "#e8eef8",
    "tech": "#f5f0e8",   "culture": "#f8e8f0",
}

TONE_MAP = {
    1: "קליל — חדשות טובות בלבד",
    2: "קצת יותר קל מהרגיל",
    3: "מאוזן — ברירת המחדל",
    4: "כנה — כלול חדשות קשות עם הקשר",
    5: "ישרות מקסימלית — אל תסנן",
}

# ── CONFIG ────────────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            print(f"Config: tone={cfg.get('tone', 3)}, blocked={cfg.get('blocked_topics', [])}")
            return cfg
        except Exception as e:
            print(f"Config error ({e}), using defaults")
    return {"tone": 3, "sections": DEFAULT_SECTIONS, "blocked_topics": [], "special_note": ""}

# ── STEP 1: SEARCH NEWS ───────────────────────────────────────────────────────

def step1_search_news(date_str, day_name, cfg):
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sections = [s for s in cfg.get("sections", DEFAULT_SECTIONS) if s.get("enabled", True)]
    blocked  = cfg.get("blocked_topics", [])

    names        = ", ".join(s["label"] for s in sections)
    blocked_line = f"דלג על: {', '.join(blocked)}." if blocked else ""

    prompt = (
        f"חפש חדשות אמיתיות של {day_name} {date_str} לעיתון ילדים ישראלי.\n"
        f"סעיפים: {names}. {blocked_line}\n"
        f"כתוב 2-3 משפטים לכל סעיף. טקסט בלבד."
    )

    text = ""
    with client.messages.stream(
        model=MODEL,
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for _ in stream:
            pass
        msg = stream.get_final_message()

    for block in msg.content:
        if hasattr(block, "text"):
            text += block.text

    print(f"Step 1 done: {len(text)} chars")
    return text

# ── STEP 2: WRITE DIGEST ──────────────────────────────────────────────────────

TOOL_SCHEMA = {
    "name": "publish_digest",
    "description": "פרסם גיליון",
    "input_schema": {
        "type": "object",
        "required": ["sections", "word_of_day", "think_question"],
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "icon", "label", "color", "stories"],
                    "properties": {
                        "id":    {"type": "string"},
                        "icon":  {"type": "string"},
                        "label": {"type": "string"},
                        "color": {"type": "string"},
                        "stories": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["tag", "tag_type", "headline", "body"],
                                "properties": {
                                    "tag":      {"type": "string"},
                                    "tag_type": {"type": "string"},
                                    "headline": {"type": "string"},
                                    "body":     {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "word_of_day": {
                "type": "object",
                "required": ["word", "definition"],
                "properties": {
                    "word":       {"type": "string"},
                    "definition": {"type": "string"},
                },
            },
            "think_question": {"type": "string"},
        },
    },
}


def step2_write_digest(news_summary, date_str, day_name, cfg):
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tone     = cfg.get("tone", 3)
    note     = cfg.get("special_note", "").strip()
    sections = [s for s in cfg.get("sections", DEFAULT_SECTIONS) if s.get("enabled", True)]

    sec_lines  = "\n".join(f"- {s['icon']} {s['label']} id={s['id']} color={SECTION_COLORS.get(s['id'],'#f0f0f0')}" for s in sections)
    note_line  = f"הערה: {note}" if note else ""

    prompt = (
        f"עורך עיתון ילדים בעברית. קוראת: ילדה בת 10 מישראל.\n"
        f"תאריך: {day_name} {date_str}. טון: {TONE_MAP[tone]}. {note_line}\n\n"
        f"חדשות היום:\n{news_summary}\n\n"
        f"סעיפים:\n{sec_lines}\n\n"
        f"כתוב כתבה אחת לכל סעיף. "
        f"בשדה body: השתמש ב-[HONEST]...[/HONEST] לעובדה מרכזית ו-[OPENQ]...[/OPENQ] למה שלא ידוע.\n"
        f"קרא ל-publish_digest."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "publish_digest":
            print("Step 2 done: tool call received")
            return block.input

    raise ValueError("publish_digest tool was not called")

# ── HTML RENDERER ─────────────────────────────────────────────────────────────

def render_body(body):
    import re
    body = re.sub(r"\[HONEST\](.*?)\[/HONEST\]", r'<div class="honest-line">\1</div>', body, flags=re.DOTALL)
    body = re.sub(r"\[OPENQ\](.*?)\[/OPENQ\]",   r'<div class="open-q">\1</div>',     body, flags=re.DOTALL)
    return body


def render_html(data, date_str, day_name):
    sections_html = ""
    for sec in data["sections"]:
        stories = ""
        for st in sec["stories"]:
            stories += f"""
      <div class="story">
        <span class="tag tag-{st.get('tag_type','world')}">{st['tag']}</span>
        <div class="story-headline">{st['headline']}</div>
        <div class="story-body">{render_body(st['body'])}</div>
        <div class="rating"><span class="rl">דרגי</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
        </div>
      </div>"""
        sections_html += f"""
  <div class="section" style="--c:{sec['color']}">
    <div class="sh"><span class="si">{sec['icon']}</span><span class="sl">{sec['label']}</span></div>
    <div class="sb">{stories}</div>
  </div>"""

    w = data["word_of_day"]
    q = data["think_question"]

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>החדשות של אמה - {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;700;900&family=Heebo:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--cream:#fdf6ec;--ink:#1a1208;--mid:#7a5c3a;--acc:#e8612c;--accl:#fde8dc;--rule:#d4c4aa;--hbg:#f7f3ee;--hbr:#c4a882}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--cream);color:var(--ink);font-family:Heebo,sans-serif;font-size:15px;line-height:1.85;direction:rtl}}
.mast{{border-bottom:3px double var(--ink);padding:22px 40px 20px;text-align:center}}
.mdate{{font-family:'Frank Ruhl Libre',serif;font-size:20px;font-weight:700;margin-bottom:4px}}
.mmeta{{display:flex;justify-content:space-between;font-size:11px;color:var(--mid);margin-bottom:14px}}
.mast h1{{font-family:'Frank Ruhl Libre',serif;font-size:clamp(46px,9vw,82px);font-weight:900;line-height:1.05}}
.mast h1 span{{color:var(--acc)}}
.msub{{font-family:'Frank Ruhl Libre',serif;font-size:16px;color:var(--mid);margin-top:8px}}
hr{{border:none;border-top:1px solid var(--rule);margin:12px auto;width:80%}}
.wrap{{max-width:820px;margin:0 auto;padding:0 24px 60px}}
.section{{margin:28px 0;border-radius:4px;overflow:hidden;border:1px solid var(--rule);animation:up .5s ease both}}
.section:nth-child(1){{animation-delay:.05s}}.section:nth-child(2){{animation-delay:.12s}}
.section:nth-child(3){{animation-delay:.19s}}.section:nth-child(4){{animation-delay:.26s}}
.section:nth-child(5){{animation-delay:.33s}}.section:nth-child(6){{animation-delay:.40s}}
@keyframes up{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:translateY(0)}}}}
.sh{{padding:14px 22px;display:flex;align-items:center;gap:14px;border-bottom:2px solid var(--rule);background:var(--c)}}
.si{{font-size:28px;flex-shrink:0}}.sl{{font-family:'Frank Ruhl Libre',serif;font-size:24px;font-weight:900}}
.sb{{padding:20px 24px;background:white}}
.story{{padding:18px 0;border-bottom:1px solid #f0e8dc}}.story:last-child{{border-bottom:none;padding-bottom:4px}}
.story-headline{{font-family:'Frank Ruhl Libre',serif;font-size:18px;font-weight:700;line-height:1.4;margin-bottom:10px}}
.story-body{{font-size:14.5px;line-height:1.9;color:#3a2e22;font-weight:300}}
.honest-line{{margin:12px 0 4px;padding:10px 14px;background:var(--hbg);border-right:3px solid var(--hbr);border-radius:0 3px 3px 0;font-size:13.5px;color:#4a3a28;line-height:1.7;font-style:italic}}
.honest-line::before{{content:"מה שאנחנו יודעים: ";font-style:normal;font-weight:700;color:var(--mid);font-size:12px}}
.open-q{{margin-top:10px;font-size:13px;color:#7a6a58;font-style:italic}}
.open-q::before{{content:"עדיין לא ידוע: ";font-style:normal;font-weight:700;font-size:12px;color:var(--acc)}}
.word-box{{background:var(--ink);color:var(--cream);border-radius:4px;padding:20px 24px;margin-bottom:20px}}
.word-box .wl{{font-size:11px;color:var(--acc);font-weight:600;margin-bottom:6px}}
.word-box .ww{{font-family:'Frank Ruhl Libre',serif;font-size:30px;font-weight:900;margin-bottom:8px;color:white}}
.word-box .wd{{font-size:13.5px;color:#c8b89a;line-height:1.7;font-weight:300}}
.think{{background:var(--accl);border-right:3px solid var(--acc);padding:16px 20px;border-radius:0 4px 4px 0}}
.think .tl{{font-size:11px;font-weight:700;color:var(--acc);margin-bottom:8px}}
.think p{{font-family:'Frank Ruhl Libre',serif;font-size:17px;line-height:1.6}}
.footer{{text-align:center;padding:28px;border-top:3px double var(--ink);font-size:12px;color:var(--mid);margin-top:20px}}
.rating{{margin-top:12px;display:flex;gap:4px;align-items:center;flex-direction:row-reverse;justify-content:flex-end}}
.rl{{font-size:11px;color:#9a8878;margin-left:6px}}
.star{{cursor:pointer;font-size:20px;color:#d4c4aa;transition:color .15s,transform .1s;user-select:none}}
.star:hover,.star.on{{color:#e8a020;transform:scale(1.2)}}
.tag{{display:inline-block;font-size:10px;font-weight:700;padding:3px 10px;border-radius:2px;margin-bottom:10px}}
.tag-world{{background:#d4eed4;color:#2d6b2d}}.tag-science{{background:#d4e4f4;color:#1e4d7a}}
.tag-tech{{background:#ede4d4;color:#6b4d1e}}.tag-israel{{background:#d4f4e8;color:#1e6b4d}}
.tag-culture{{background:#f4d4e8;color:#6b1e4d}}.tag-complex{{background:#ede0d4;color:#7a3a1a}}
@media(max-width:580px){{.mast{{padding:18px 16px 16px}}.wrap{{padding:0 12px 40px}}.sb{{padding:14px 16px}}.sl{{font-size:20px}}}}
</style>
</head>
<body>
<div class="mast">
  <div class="mdate">{day_name}, {date_str}</div>
  <hr>
  <h1>החדשות <span>של אמה</span></h1>
  <div class="msub">כל החדשות שחשוב לדעת — רק בשבילך</div>
  <hr>
  <div class="mmeta"><span>מהדורה אישית</span><span>גיליון יומי</span></div>
</div>
<div class="wrap">
{sections_html}
  <div class="section" style="--c:#f5f0e8">
    <div class="sh"><span class="si">💬</span><span class="sl">מילה ותהייה</span></div>
    <div class="sb">
      <div class="word-box">
        <div class="wl">מילה של היום</div>
        <div class="ww">{w['word']}</div>
        <div class="wd">{w['definition']}</div>
      </div>
      <div class="think">
        <div class="tl">משהו לחשוב עליו — לשיחת ערב</div>
        <p>{q}</p>
      </div>
    </div>
  </div>
</div>
<div class="footer">החדשות של אמה · {day_name}, {date_str} · נעשה באהבה ❤️ רק בשבילך</div>
<script>
function rate(s){{
  const all=s.parentElement.querySelectorAll('.star'),i=Array.from(all).indexOf(s);
  all.forEach((x,j)=>x.classList.toggle('on',j<=i));
}}
</script>
</body>
</html>"""

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    import zoneinfo
    tz    = zoneinfo.ZoneInfo("Asia/Jerusalem")
    today = datetime.datetime.now(tz).date()

    day_names = {0:"יום שני",1:"יום שלישי",2:"יום רביעי",3:"יום חמישי",4:"יום שישי",5:"שבת",6:"יום ראשון"}
    months    = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]

    day_name = day_names[today.weekday()]
    date_str = f"{today.day} ב{months[today.month-1]} {today.year}"
    slug     = today.strftime("%Y-%m-%d")

    cfg = load_config()
    print(f"Generating digest for {date_str}...")

    print("Step 1: searching news...")
    news = step1_search_news(date_str, day_name, cfg)

    print("Waiting 90s for rate limit window to reset...")
    time.sleep(90)

    print("Step 2: writing digest...")
    data = step2_write_digest(news, date_str, day_name, cfg)

    html = render_html(data, date_str, day_name)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Done → docs/{slug}.html")


if __name__ == "__main__":
    main()
