"""Group the same story reported by several sources into one cluster."""
import re
from datetime import timedelta
from util import parse_iso

STOP = set("""the a an of to in on for and as at by with is are was be after from over says how why what his her their into
של על את עם לא זה זו היא הוא אל גם כי או מה מי אם יש אין אבל בין אחרי לפני הם הן אני אתה היה היו יהיה עוד כל כבר רק כך נגד מול
בעקבות בגלל לקראת אצל אך עד מאז דווח צפו תיעוד""".split())
_PUNCT = re.compile(r"[^\w\s]", re.U)


def tokens(title):
    t = _PUNCT.sub(" ", (title or "").lower())
    out = set()
    for w in t.split():
        if len(w) < 2 or w in STOP or w.isdigit() and len(w) < 3:
            continue
        if re.match(r"[֐-׿]", w) and len(w) > 3 and w[0] in "והבלמשכ":
            out.add(w[1:])  # Hebrew prefix letter: "ולמכבי" -> "למכבי" (one level only)
        out.add(w)
    return out


def similar(a, b):
    if len(a) < 3 or len(b) < 3:
        return False
    inter = len(a & b)
    if inter < 3:
        return False
    jac = inter / len(a | b)
    cont = inter / min(len(a), len(b))
    return jac >= 0.5 or cont >= 0.75


def cluster(articles, window_hours=36):
    """Assign a['cluster'] = id of the cluster's primary article (earliest, image preferred)."""
    arts = sorted(articles, key=lambda a: a["published"])
    toks = {a["id"]: tokens(a["title"]) for a in arts}
    parent = {a["id"]: a["id"] for a in arts}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    win = timedelta(hours=window_hours)
    for i, a in enumerate(arts):
        ta = parse_iso(a["published"])
        for j in range(i - 1, -1, -1):
            b = arts[j]
            if ta - parse_iso(b["published"]) > win:
                break
            if a["lang"] != b["lang"] or a.get("ticker") != b.get("ticker"):
                continue
            if similar(toks[a["id"]], toks[b["id"]]):
                parent[find(a["id"])] = find(b["id"])
    groups = {}
    for a in arts:
        groups.setdefault(find(a["id"]), []).append(a)
    for members in groups.values():
        primary = sorted(members, key=lambda a: (not bool(a.get("image")), a["published"]))[0]
        names = []
        for m in members:
            for n in m["sources"]:
                if n not in names:
                    names.append(n)
        for m in members:
            m["cluster"] = primary["id"]
            m["cluster_size"] = len(members)
            m["cluster_sources"] = names
    return len([g for g in groups.values() if len(g) > 1])
