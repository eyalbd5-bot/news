"""Hebrew title/summary/digest for foreign articles via Gemini (free tier), batched and cached."""
import json, os, time, urllib.request, urllib.error
import re
from util import has_hebrew
_BAD = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")  # Arabic letters: the model sometimes slips one into Hebrew text

MODELS = ["gemini-flash-lite-latest", "gemini-flash-latest"]
BATCH = 5
PAUSE = 4.5          # seconds between requests: stays under 15 RPM on the free tier
MAX_BODY = 6000      # chars of body sent per article

PROMPT = """אתה עורך חדשות ישראלי. לכל פריט במערך קלט תחזיר אובייקט JSON עם השדות:
- id: כפי שניתן.
- title_he: הכותרת בעברית עיתונאית, קצרה וברורה. שמות אנשים וקבוצות בתעתיק המקובל בתקשורת הישראלית (ברצלונה, מנצ'סטר יונייטד, מילאן). שמות חברות ומוצרים טכנולוגיים נשארים באנגלית (OpenAI, Nvidia, GPT).
- summary_he: משפט אחד עד שניים שמסכמים את הידיעה.
- digest_he: תקציר מלא בעברית של הכתבה, 120 עד 220 מילים, ב-2 עד 4 פסקאות מופרדות בשורה ריקה, נאמן לעובדות שבמקור בלבד. אם אין גוף כתבה, 2 עד 3 משפטים על בסיס הכותרת והתקציר.
אין להוסיף דעות או מידע שלא במקור. אין להשתמש בקו מפריד ארוך (—), רק במקף רגיל. החזר אך ורק מערך JSON תקין.

קלט:
"""

SCHEMA = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "id": {"type": "STRING"}, "title_he": {"type": "STRING"}, "summary_he": {"type": "STRING"}, "digest_he": {"type": "STRING"}},
    "required": ["id", "title_he", "summary_he", "digest_he"]}}


def _call(model, key, text):
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0.2}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                                 data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return json.loads(d["candidates"][0]["content"]["parts"][0]["text"]), d.get("usageMetadata", {})


def translate_batch(items, key, log):
    """items: [{id,title,summary,body}] -> {id: {title_he,summary_he,digest_he}}"""
    text = PROMPT + json.dumps(items, ensure_ascii=False)
    for model in MODELS:
        for attempt in range(3):
            try:
                out, usage = _call(model, key, text)
                res = {}
                for o in out if isinstance(out, list) else []:
                    vals = [o.get("title_he", ""), o.get("summary_he", ""), o.get("digest_he", "")]
                    if o.get("id") and has_hebrew(vals[0]) and has_hebrew(vals[2]) and not any(_BAD.search(v) for v in vals):
                        res[o["id"]] = o
                log["tokens"] += usage.get("totalTokenCount", 0)
                return res
            except urllib.error.HTTPError as e:
                code = e.code
                log["errors"].append(f"{model} HTTP {code}")
                if code == 429:
                    time.sleep(20 * (attempt + 1))
                    continue
                if code >= 500:
                    time.sleep(5)
                    continue
                break  # 400/403: try the next model
            except Exception as e:  # noqa
                log["errors"].append(f"{model} {type(e).__name__}")
                time.sleep(5)
    return {}


def translate_pending(articles, bodies, max_requests):
    """articles: foreign ones with he == None, newest first. bodies: id -> text (may be missing).
    Fills a['he'] and returns {id: digest_he} plus a log."""
    key = os.environ.get("GEMINI_API_KEY")
    log = {"requests": 0, "translated": 0, "tokens": 0, "errors": [], "skipped_no_key": not key}
    digests = {}
    if not key:
        return digests, log
    pending = [a for a in articles if a["lang"] != "he" and not a.get("he") and a.get("he_tries", 0) < 3]
    pending.sort(key=lambda a: a["published"], reverse=True)
    for i in range(0, len(pending), BATCH):
        if log["requests"] >= max_requests:
            break
        chunk = pending[i:i + BATCH]
        items = [{"id": a["id"], "title": a["title"], "summary": a["summary"][:600],
                  "body": (bodies.get(a["id"]) or "")[:MAX_BODY]} for a in chunk]
        res = translate_batch(items, key, log)
        log["requests"] += 1
        for a in chunk:
            r = res.get(a["id"])
            if r:
                a["he"] = {"title": r["title_he"].replace("—", "-").strip(), "summary": r["summary_he"].replace("—", "-").strip()}
                digests[a["id"]] = r["digest_he"].replace("—", "-").strip()
                log["translated"] += 1
            else:
                a["he_tries"] = a.get("he_tries", 0) + 1
        time.sleep(PAUSE)
    log["pending_after"] = sum(1 for a in articles if a["lang"] != "he" and not a.get("he"))
    return digests, log
