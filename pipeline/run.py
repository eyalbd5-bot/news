"""One refresh: fetch -> extract -> tag -> cluster -> translate -> prune -> write. Idempotent."""
import os, sys, time
from datetime import timedelta
from util import (ROOT, INDEX_DIR, BODY_DIR, META, load_env, load_config, load_json, save_json, now_utc, iso, parse_iso)
from sources import fetch_all
from extract import extract_many
from dedupe import cluster
from translate import translate_pending
from tags import build_taggers, tag

MAX_EXTRACT = int(os.environ.get("MAX_EXTRACT", "150"))
MAX_TRANSLATE_REQUESTS = int(os.environ.get("MAX_TRANSLATE_REQUESTS", "60"))


def main():
    t0 = time.time()
    load_env()
    cfg = load_config()
    keep = timedelta(days=cfg["site"].get("keep_days", 7))
    now = now_utc()
    report = {"updated": iso(now), "topics": {}, "sources": [], "new": 0, "extracted": 0, "clusters": 0}

    # 1. existing state
    index = {}
    for t in cfg["topics"]:
        for a in load_json(INDEX_DIR / f"{t['id']}.json", []):
            index[a["id"]] = a
    bodies = {}  # id -> body dict loaded lazily

    def body_of(aid):
        if aid not in bodies:
            bodies[aid] = load_json(BODY_DIR / f"{aid}.json", None)
        return bodies[aid]

    # 2. fetch
    fetched, status = fetch_all(cfg)
    report["sources"] = status
    src_cfg = {s["id"]: s for t in cfg["topics"] for s in t["sources"]}
    new = []
    for a in fetched:
        max_age = timedelta(days=src_cfg[a["source"]].get("max_age_days", cfg["site"].get("keep_days", 7)))
        if now - parse_iso(a["published"]) > max_age:
            continue
        cur = index.get(a["id"])
        if cur:
            if a["source_name"] not in cur["sources"]:
                cur["sources"].append(a["source_name"])
            if not cur.get("image") and a.get("image"):
                cur["image"] = a["image"]
            if not cur.get("summary") and a.get("summary"):
                cur["summary"] = a["summary"]
            continue
        index[a["id"]] = a
        new.append(a)
    report["new"] = len(new)

    # 3. extract bodies for new articles (newest first, capped), plus retry of untried ones
    todo = [a for a in index.values() if not a.get("no_body") and not a.get("extract_tried")]
    todo.sort(key=lambda a: a["published"], reverse=True)
    todo = todo[:MAX_EXTRACT]
    texts = extract_many(todo)
    for aid, text in texts.items():
        save_json(BODY_DIR / f"{aid}.json", {"id": aid, "text": text}, compact=True)
        bodies[aid] = {"id": aid, "text": text}
    report["extracted"] = len(texts)
    report["extract_failed"] = len(todo) - len(texts)

    # 4. tags (football) and 5. clusters, per topic
    for t in cfg["topics"]:
        arts = [a for a in index.values() if a["topic"] == t["id"]]
        if t.get("teams") or t.get("leagues"):
            taggers = build_taggers(t)
            for a in arts:
                if a in new or not a.get("tags"):
                    b = body_of(a["id"])
                    tag(a, taggers, b["text"] if b else "")
        report["clusters"] += cluster(arts)

    # 6. translate
    foreign = [a for a in index.values() if a["lang"] != "he"]
    text_by_id = {a["id"]: (body_of(a["id"]) or {}).get("text", "") for a in foreign if not a.get("he")}
    digests, tlog = translate_pending(foreign, text_by_id, MAX_TRANSLATE_REQUESTS)
    for aid, dg in digests.items():
        b = body_of(aid) or {"id": aid, "text": ""}
        b["digest_he"] = dg
        save_json(BODY_DIR / f"{aid}.json", b, compact=True)
    report["translate"] = tlog

    # 7. prune + write
    keep_ids = set()
    for t in cfg["topics"]:
        arts = [a for a in index.values() if a["topic"] == t["id"] and now - parse_iso(a["published"]) <= keep]
        arts.sort(key=lambda a: a["published"], reverse=True)
        keep_ids.update(a["id"] for a in arts)
        save_json(INDEX_DIR / f"{t['id']}.json", arts, compact=True)
        report["topics"][t["id"]] = {"count": len(arts), "with_body": sum(1 for a in arts if a.get("has_body")),
                                     "translated": sum(1 for a in arts if a["lang"] != "he" and a.get("he")),
                                     "foreign": sum(1 for a in arts if a["lang"] != "he")}
    removed = 0
    for p in BODY_DIR.glob("*.json"):
        if p.stem not in keep_ids:
            p.unlink(); removed += 1
    report["pruned_bodies"] = removed
    report["seconds"] = round(time.time() - t0, 1)
    save_json(META, report)

    ok = sum(1 for s in status if s["ok"])
    print(f"sources ok {ok}/{len(status)} | new {report['new']} | extracted {report['extracted']} (failed {report['extract_failed']}) "
          f"| clusters {report['clusters']} | translated {tlog['translated']} in {tlog['requests']} req, {tlog['tokens']} tokens, pending {tlog.get('pending_after')} "
          f"| {report['seconds']}s")
    for s in status:
        if not s["ok"]:
            print("  FAILED", s["name"], s["error"])
    for t, v in report["topics"].items():
        print(f"  {t}: {v}")
    if tlog["errors"]:
        print("  translate errors:", tlog["errors"][:5])


if __name__ == "__main__":
    main()
