"""Pull the full article text (and a fallback image) from the source page."""
import concurrent.futures as cf, re
import trafilatura
from util import http_get

_OG = re.compile(r'<meta[^>]+property="og:image(?::url)?"[^>]+content="([^"]+)"', re.I)
_OG2 = re.compile(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image(?::url)?"', re.I)
MAX_CHARS = 20000


def extract(url):
    html = http_get(url, timeout=25, retries=1).decode("utf-8", errors="ignore")
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_recall=True) or ""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    m = _OG.search(html) or _OG2.search(html)
    image = m.group(1) if m else None
    if len(text) < 200:
        text = ""
    return text[:MAX_CHARS], image


def extract_many(articles, threads=8):
    """articles: list to enrich in place. Returns dict id -> text."""
    bodies = {}

    def run(a):
        try:
            text, img = extract(a["url"])
            return a, text, img, None
        except Exception as e:  # noqa
            return a, "", None, f"{type(e).__name__}"

    with cf.ThreadPoolExecutor(threads) as ex:
        for a, text, img, err in ex.map(run, articles):
            a["has_body"] = bool(text)
            if not a.get("image") and img:
                a["image"] = img
            if text:
                bodies[a["id"]] = text
            a["extract_tried"] = True
            if err:
                a["extract_error"] = err
    return bodies
