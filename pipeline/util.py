"""Shared helpers: paths, config, http, json, ids, dates."""
import hashlib, json, os, re, ssl, tempfile, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
DATA = ROOT / "data"
INDEX_DIR = DATA / "index"
BODY_DIR = DATA / "body"
META = DATA / "meta.json"

ssl._create_default_https_context = ssl._create_unverified_context
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept": "*/*", "Accept-Language": "he,en;q=0.8"}


def load_env():
    """Read .env (KEY=VALUE lines) into os.environ without overriding real env."""
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj, compact=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def http_get(url, timeout=20, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa
            last = e
            if getattr(e, "code", None) in (403, 404, 405, 410):
                break
            time.sleep(1.5 * (i + 1))
    raise last


_TRACK = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_|source$|at_|ns_|cmp|ito|__twitter|mc_)", re.I)


def clean_url(url):
    """Strip tracking params and fragments so the same story has one id across sources."""
    url = (url or "").strip()
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if not _TRACK.match(k)]
    path = u.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((u.scheme.lower() or "https", u.netloc.lower().replace("www.", ""), path,
                                    urllib.parse.urlencode(q), ""))


def article_id(url):
    return hashlib.sha1(clean_url(url).encode("utf-8")).hexdigest()[:12]


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>|</p>", " ", s, flags=re.I)
    s = _TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&#8217;", "’").replace("&#8220;", "“").replace("&#8221;", "”"))
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    return _WS.sub(" ", s).strip()


HEB = re.compile(r"[֐-׿]")


def has_hebrew(s):
    return bool(HEB.search(s or ""))
