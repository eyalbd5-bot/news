"""Fetch every configured source into a flat list of normalised articles."""
import concurrent.futures as cf, json, re, time
from datetime import datetime, timezone, timedelta
import feedparser
from util import http_get, strip_html, clean_url, article_id, iso, now_utc

_IMG = re.compile(r'<img[^>]+src="([^"]+)"', re.I)


def _entry_image(e):
    for k in ("media_content", "media_thumbnail"):
        for m in e.get(k) or []:
            u = m.get("url")
            if u and not u.endswith(".svg"):
                return u
    for enc in e.get("enclosures") or []:
        if "image" in (enc.get("type") or "") and enc.get("href"):
            return enc["href"]
    for blob in [e.get("summary", "")] + [c.get("value", "") for c in e.get("content") or []]:
        m = _IMG.search(blob or "")
        if m:
            return m.group(1)
    return None


def _entry_summary(e):
    cands = [e.get("summary", ""), e.get("description", "")] + [c.get("value", "") for c in e.get("content") or []]
    for c in cands:
        t = strip_html(c)
        if len(t) > 20:
            return t[:700]
    return ""


def _entry_date(e):
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        tp = e.get(k)
        if tp:
            try:
                return datetime(*tp[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return now_utc()


def fetch_rss(src, topic):
    raw = http_get(src["url"])
    f = feedparser.parse(raw)
    out = []
    for e in f.entries:
        url = e.get("link") or ""
        title = strip_html(e.get("title", ""))
        if not url or not title:
            continue
        out.append(_mk(src, topic, url, title, _entry_summary(e), _entry_image(e), _entry_date(e)))
    return out


def fetch_scores365(src, topic):
    raw = http_get(src["url"])
    d = json.loads(raw)
    out = []
    for n in d.get("news", []):
        url, title = n.get("url"), (n.get("title") or "").strip()
        if not url or not title:
            continue
        try:
            dt = datetime.fromisoformat(n["publishDate"]).astimezone(timezone.utc)
        except Exception:
            dt = now_utc()
        out.append(_mk(src, topic, url, title, "", n.get("image"), dt))
    return out


def _mk(src, topic, url, title, summary, image, dt):
    url = clean_url(url)
    return {
        "id": article_id(url), "topic": topic["id"], "section": src["section"],
        "source": src["id"], "source_name": src["name"], "sources": [src["name"]],
        "lang": src.get("lang", "en"), "title": title, "summary": summary, "url": url,
        "image": image, "published": iso(min(dt, now_utc() + timedelta(minutes=5))), "fetched": iso(now_utc()),
        "ticker": bool(src.get("ticker")), "official": src["section"] == "official",
        "no_body": bool(src.get("no_body")), "tags": {}, "cluster": None, "has_body": False, "he": None,
    }


FETCHERS = {"rss": fetch_rss, "scores365": fetch_scores365}


def fetch_all(config):
    jobs = [(t, s) for t in config["topics"] for s in t["sources"]]
    status, articles = [], []

    def run(job):
        topic, src = job
        t0 = time.time()
        try:
            items = FETCHERS[src.get("type", "rss")](src, topic)
            return src, items, None, time.time() - t0
        except Exception as e:  # noqa
            return src, [], f"{type(e).__name__}: {str(e)[:120]}", time.time() - t0

    with cf.ThreadPoolExecutor(10) as ex:
        for src, items, err, dt in ex.map(run, jobs):
            status.append({"id": src["id"], "name": src["name"], "ok": err is None, "count": len(items),
                           "error": err, "seconds": round(dt, 1)})
            articles.extend(items)
    return articles, status
