"""Pull the full article text (and a fallback image) from the source page."""
import concurrent.futures as cf, re
import trafilatura
from util import http_get

_OG = re.compile(r'<meta[^>]+property="og:image(?::url)?"[^>]+content="([^"]+)"', re.I)
_OG2 = re.compile(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image(?::url)?"', re.I)
MAX_CHARS = 20000


def fetch_html(url):
    return http_get(url, timeout=25, retries=1).decode("utf-8", errors="ignore")


def parse(html):
    """lxml is not safe to run from several threads at once (a cloud run died with heap corruption
    on 07/11/2026), so parsing happens on the main thread; only the downloads are parallel."""
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_recall=True) or ""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    m = _OG.search(html) or _OG2.search(html)
    image = m.group(1) if m else None
    if len(text) < 200:
        text = ""
    return text[:MAX_CHARS], image


def extract(url):
    return parse(fetch_html(url))


def extract_many(articles, threads=8):
    """articles: list to enrich in place. Returns dict id -> text."""
    bodies = {}

    def fetch(a):
        try:
            return a, fetch_html(a["url"]), None
        except Exception as e:  # noqa
            return a, None, f"{type(e).__name__}"

    with cf.ThreadPoolExecutor(threads) as ex:
        pages = list(ex.map(fetch, articles))
    for a, html, err in pages:
        text, img = ("", None)
        if html is not None:
            try:
                text, img = parse(html)
            except Exception as e:  # noqa
                err = f"parse {type(e).__name__}"
        a["has_body"] = bool(text)
        if not a.get("image") and img:
            a["image"] = img
        if text:
            bodies[a["id"]] = text
        a["extract_tried"] = True
        if err:
            a["extract_error"] = err
    return bodies
