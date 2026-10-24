"""Team / league tags for football articles from configured keywords."""
import re


def _compile(keywords):
    pats = []
    for k in keywords:
        k = k.strip()
        if re.match(r"[A-Za-z]", k):
            pats.append(re.compile(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", re.I))
        else:
            pats.append(re.compile(re.escape(k)))
    return pats


def build_taggers(topic):
    return {"teams": [(t["id"], _compile(t["keywords"])) for t in topic.get("teams", [])],
            "leagues": [(l["id"], _compile(l["keywords"])) for l in topic.get("leagues", [])]}


def tag(article, taggers, body=""):
    text = " ".join([article["title"], article.get("summary", ""), (body or "")[:1500]])
    title_only = article["title"] + " " + article.get("summary", "")
    out = {}
    for kind, entries in taggers.items():
        hits = []
        for tid, pats in entries:
            # teams need a hit in title/summary (body mentions are too loose); leagues may use the body
            hay = title_only if kind == "teams" else text
            if any(p.search(hay) for p in pats):
                hits.append(tid)
        if hits:
            out[kind] = hits
    article["tags"] = out
