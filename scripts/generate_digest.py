#!/usr/bin/env python3
"""
החדשות של אמה — Daily Digest Generator
Step 1: Search today's news (with web search tool)
Step 2: Write the digest as JSON (no web search, fast and reliable)
"""

import os
import json
import time
import datetime
import anthropic
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OUTPUT_DIR = Path("docs")
CONFIG_FILE = Path("docs/config.json")

DEFAULT_SECTIONS = [
    {"id":"israel",  "icon":"🇮🇱", "label":"קרוב לבית",     "enabled":True},
    {"id":"world",   "icon":"🌍",  "label":"מבט על העולם",   "enabled":True},
    {"id":"science", "icon":"🔬",  "label":"גילוי היום",      "enabled":True},
    {"id":"tech",    "icon":"💡",  "label":"זרקור טכנולוגי", "enabled":True},
    {"id":"culture", "icon":"🎨",  "label":"פינת תרבות",     "enabled":True},
]

SECTION_COLORS = {
    "israel":"#e8f4f0","world":"#e8f4e8","science":"#e8eef8",
    "tech":"#f5f0e8","culture":"#f8e8f0",
}

TONE_MAP = {
    1:"קליל — חדשות טובות בלבד",
    2:"קצת יותר קל מהרגיל",
    3:"מאוזן — ברירת המחדל",
    4:"כנה — כלול חדשות קשות עם הקשר",
    5:"ישרות מקסימלית — אל תסנן",
}


def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            print(f"Loaded config: tone={cfg.get('tone',3)}")
            return cfg
        except Exception as e:
            print(f"Config error: {e}")
    return {"tone":3,"sections":DEFAULT_SECTIONS,"blocked_topics":[],"special_note":""}


def step1_search_news(date_str, day_name, cfg):
    """Search today's news and return a plain text summary."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    blocked = cfg.get("blocked_topics", [])
    sections = [s for s in cfg.get("sections", DEFAULT_SECTIONS) if s.get("enabled", True)]
    section_names = ", ".join([s["label"] for s in sections])
    blocked_line = f"אל תכלול: {', '.join(blocked)}." if blocked else ""

    prompt = f"""חפש חדשות אמיתיות של היום {day_name} {date_str} עבור עיתון ילדים ישראלי.
אסוף חדשות עבור הסעיפים: {section_names}.
{blocked_line}
כתוב תקציר עברי קצר של 3-5 משפטים לכל סעיף. טקסט פשוט בלבד, ללא JSON."""

    text = ""
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for event in stream:
            pass
        message = stream.get_final_message()

    for block in message.content:
        if hasattr(block, 'text'):
            text += block.text

    print(f"News summary: {len(text)} chars")
    return text


def step2_write_digest(news_summary, date_str, day_name, cfg):
    """Write the digest as clean JSON based on the news summary. No web search."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    tone = cfg.get("tone", 3)
    note = cfg.get("special_note", "").strip()
    sections = [s for s in cfg.get("sections", DEFAULT_SECTIONS) if s.get("enabled", True)]

    section_json = ",".join([
        f'{{"id":"{s["id"]}","icon":"{s["icon"]}","label":"{s["label"]}",'
        f'"color":"{SECTION_COLORS.get(s["id"],"#f0f0f0")}",'
        f'"stories":[{{"tag":"נושא","tag_type":"{s["id"]}","headline":"כותרת","body":"תוכן"}}]}}'
        for s in sections
    ])

    note_line = f"הערה: {note}" if note else ""

    prompt = f"""אתה עורך עיתון ילדים בעברית. הקוראת היא ילדה בת 10 חכמה מישראל.
תאריך: {day_name}, {date_str}. טון: {TONE_MAP[tone]}. {note_line}

להלן תקציר חדשות היום:
{news_summary}

כתוב גיליון ילדים מבוסס על החדשות האלה.
עקרונות: קרא לדברים בשמם. פנה לתגובה האנושית. אל תציין נפגעים. אי-ודאות היא כנה.
השתמש ב-[HONEST]טקסט[/HONEST] לעובדה מרכזית ו-[OPENQ]טקסט[/OPENQ] למה שלא ידוע.

החזר JSON בלבד. אסור להשתמש במרכאות " בתוך ערכי הטקסט — השתמש ב-׳ בלבד.

{{"sections":[{section_json}],"word_of_day":{{"word":"מילה","definition":"הגדרה"}},"think_question":"שאלה"}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    print(f"Digest text: {len(text)} chars")

    if "```" in text:
        start = text.find("```")
        end   = text.rfind("```")
        if start != end:
            text = text[start:end].split("\n", 1)[1]

    text = text.strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end+1]

    return json.loads(text)


def render_story_body(body):
    import re
    body = re.sub(r'\[HONEST\](.*?)\[/HONEST\]', r'<div class="honest-line">\1</div>', body, flags=re.DOTALL)
    body = re.sub(r'\[OPENQ\](.*?)\[/OPENQ\]',   r'<div class="open-q">\1</div>',     body, flags=re.DOTALL)
    return body


def render_html(data, date_str, day_name):
    sections_html = ""
    for section in data["sections"]:
        stories_html = ""
        for story in section["stories"]:
            body = render_story_body(story["body"])
            stories_html += f"""
      <div class="story">
        <span class="tag tag-{story.get('tag_type','world')}">{story['tag']}</span>
        <div class="story-headline">{story['headline']}</div>
        <div class="story-body">{body}</div>
        <div class="rating"><span class="rating-label">דרגי</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
          <span class="star" onclick="rate(this)">★</span>
        </div>
      </div>"""
        sections_html += f"""
  <div class="section" style="--section-color:{section['color']}">
    <div class="section-header">
      <span class="section-icon">{section['icon']}</span>
      <span class="section-label">{section['label']}</span>
    </div>
    <div class="section-body">{stories_html}</div>
  </div>"""

    w = data["word_of_day"]
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>החדשות של אמה - {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;700;900&family=Heebo:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--cream:#fdf6ec;--ink:#1a1208;--warm-mid:#7a5c3a;--accent:#e8612c;--accent-light:#fde8dc;--rule:#d4c4aa;--honest-bg:#f7f3ee;--honest-border:#c4a882;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--cream);color:var(--ink);font-family:'Heebo',sans-serif;font-size:15px;line-height:1.85;direction:rtl;}}
.masthead{{border-bottom:3px double var(--ink);padding:22px 40px 20px;text-align:center;background:var(--cream);}}
.masthead-date{{font-family:'Frank Ruhl Libre',serif;font-size:20px;font-weight:700;color:var(--ink);margin-bottom:4px;}}
.masthead-meta{{display:flex;justify-content:space-between;font-size:11px;color:var(--warm-mid);font-weight:500;margin-bottom:14px;}}
.masthead h1{{font-family:'Frank Ruhl Libre',serif;font-size:clamp(46px,9vw,82px);font-weight:900;line-height:1.05;color:var(--ink);}}
.masthead h1 span{{color:var(--accent);}}
.masthead-sub{{font-family:'Frank Ruhl Libre',serif;font-size:16px;color:var(--warm-mid);margin-top:8px;}}
.rule-thin{{border:none;border-top:1px solid var(--rule);margin:12px auto;width:80%;}}
.container{{max-width:820px;margin:0 auto;padding:0 24px 60px;}}
.section{{margin:28px 0;border-radius:4px;overflow:hidden;border:1px solid var(--rule);animation:fadeUp 0.5s ease both;}}
.section:nth-child(1){{animation-delay:0.05s}}.section:nth-child(2){{animation-delay:0.12s}}
.section:nth-child(3){{animation-delay:0.19s}}.section:nth-child(4){{animation-delay:0.26s}}
.section:nth-child(5){{animation-delay:0.33s}}.section:nth-child(6){{animation-delay:0.40s}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:translateY(0)}}}}
.section-header{{padding:14px 22px;display:flex;align-items:center;gap:14px;border-bottom:2px solid var(--rule);background:var(--section-color);}}
.section-icon{{font-size:28px;line-height:1;flex-shrink:0;}}
.section-label{{font-family:'Frank Ruhl Libre',serif;font-size:24px;font-weight:900;color:var(--ink);}}
.section-body{{padding:20px 24px;background:white;}}
.story{{padding:18px 0;border-bottom:1px solid #f0e8dc;}}.story:last-child{{border-bottom:none;padding-bottom:4px;}}
.story-headline{{font-family:'Frank Ruhl Libre',serif;font-size:18px;font-weight:700;line-height:1.4;color:var(--ink);margin-bottom:10px;}}
.story-body{{font-size:14.5px;line-height:1.9;color:#3a2e22;font-weight:300;}}
.story-body strong{{font-weight:600;color:var(--ink);}}
.honest-line{{margin:12px 0 4px;padding:10px 14px;background:var(--honest-bg);border-right:3px solid var(--honest-border);border-radius:0 3px 3px 0;font-size:13.5px;color:#4a3a28;line-height:1.7;font-style:italic;}}
.honest-line::before{{content:"מה שאנחנו יודעים: ";font-style:normal;font-weight:700;color:var(--warm-mid);font-size:12px;}}
.open-q{{margin-top:10px;font-size:13px;color:#7a6a58;font-style:italic;}}
.open-q::before{{content:"עדיין לא ידוע: ";font-style:normal;font-weight:700;font-size:12px;color:var(--accent);}}
.word-box{{background:var(--ink);color:var(--cream);border-radius:4px;padding:20px 24px;margin-bottom:20px;}}
.word-box .label{{font-size:11px;color:var(--accent);font-weight:600;margin-bottom:6px;}}
.word-box .word{{font-family:'Frank Ruhl Libre',serif;font-size:30px;font-weight:900;margin-bottom:8px;color:white;}}
.word-box .definition{{font-size:13.5px;color:#c8b89a;line-height:1.7;font-weight:300;}}
.think-box{{background:var(--accent-light);border-right:3px solid var(--accent);padding:16px 20px;border-radius:0 4px 4px 0;}}
.think-box .label{{font-size:11px;font-weight:700;color:var(--accent);margin-bottom:8px;}}
.think-box p{{font-family:'Frank Ruhl Libre',serif;font-size:17px;line-height:1.6;color:var(--ink);}}
.footer{{text-align:center;padding:28px;border-top:3px double var(--ink);font-size:12px;color:var(--warm-mid);font-weight:500;margin-top:20px;}}
.rating{{margin-top:12px;display:flex;gap:4px;align-items:center;flex-direction:row-reverse;justify-content:flex-end;}}
.rating-label{{font-size:11px;color:#9a8878;margin-left:6px;font-weight:500;}}
.star{{cursor:pointer;font-size:20px;color:#d4c4aa;transition:color 0.15s,transform 0.1s;user-select:none;}}
.star:hover,.star.active{{color:#e8a020;transform:scale(1.2);}}
.tag{{display:inline-block;font-size:10px;font-weight:700;padding:3px 10px;border-radius:2px;margin-bottom:10px;}}
.tag-world{{background:#d4eed4;color:#2d6b2d;}}.tag-science{{background:#d4e4f4;color:#1e4d7a;}}
.tag-tech{{background:#ede4d4;color:#6b4d1e;}}.tag-israel{{background:#d4f4e8;color:#1e6b4d;}}
.tag-complex{{background:#ede0d4;color:#7a3a1a;}}.tag-culture{{background:#f4d4e8;color:#6b1e4d;}}
@media(max-width:580px){{.masthead{{padding:18px 16px 16px}}.container{{padding:0 12px 40px}}.section-body{{padding:14px 16px}}.section-label{{font-size:20px}}}}
</style>
</head>
<body>
<div class="masthead">
  <div class="masthead-date">{day_name}, {date_str}</div>
  <hr class="rule-thin">
  <h1>החדשות <span>של אמה</span></h1>
  <div class="masthead-sub">כל החדשות שחשוב לדעת - רק בשבילך</div>
  <hr class="rule-thin">
  <div class="masthead-meta"><span>מהדורה אישית</span><span>גיליון יומי</span></div>
</div>
<div class="container">
{sections_html}
  <div class="section" style="border-color:var(--rule)">
    <div class="section-header" style="background:#f5f0e8">
      <span class="section-icon">💬</span>
      <span class="section-label">מילה ותהייה</span>
    </div>
    <div class="section-body">
      <div class="word-box">
        <div class="label">מילה של היום</div>
        <div class="word">{w['word']}</div>
        <div class="definition">{w['definition']}</div>
      </div>
      <div class="think-box">
        <div class="label">משהו לחשוב עליו - לשיחת ערב</div>
        <p>{data['think_question']}</p>
      </div>
    </div>
  </div>
</div>
<div class="footer">החדשות של אמה · {day_name}, {date_str} · נעשה באהבה ❤️ רק בשבילך</div>
<script>
function rate(star){{
  const stars=star.parentElement.querySelectorAll('.star');
  const idx=Array.from(stars).indexOf(star);
  stars.forEach((s,i)=>{{if(i<=idx)s.classList.add('active');else s.classList.remove('active');}});
}}
</script>
</body>
</html>"""


def main():
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Jerusalem")
    today = datetime.datetime.now(tz).date()

    day_names = {0:"יום שני",1:"יום שלישי",2:"יום רביעי",3:"יום חמישי",4:"יום שישי",5:"שבת",6:"יום ראשון"}
    months    = ['ינואר','פברואר','מרץ','אפריל','מאי','יוני','יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר']

    day_name = day_names[today.weekday()]
    date_str = f"{today.day} ב{months[today.month-1]} {today.year}"
    slug     = today.strftime("%Y-%m-%d")

    cfg = load_config()
    print(f"Generating digest for {date_str}...")

    # Step 1: search news (with web search, plain text output)
    print("Step 1: Searching today's news...")
    news_summary = step1_search_news(date_str, day_name, cfg)

    # Wait for rate limit window to reset before second API call
    print("Waiting 60s for rate limit to reset...")
    time.sleep(60)

    # Step 2: write digest as JSON (no web search, fast and reliable)
    print("Step 2: Writing digest...")
    data = step2_write_digest(news_summary, date_str, day_name, cfg)

    html = render_html(data, date_str, day_name)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Done! Published to docs/{slug}.html")


if __name__ == "__main__":
    main()
