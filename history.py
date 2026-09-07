# history.py — cross-run memory of papers already listed in a digest.
#
# The weekly searches legitimately re-return old papers: PubMed treats a
# year-only publication date as matching any date range inside that year, and
# Semantic Scholar author feeds often carry no publication date at all. Rather
# than fight the metadata, the pipeline remembers every paper it has listed in
# a sent digest (in _seen.json under data_dir) and drops those papers before
# scoring. Stdlib-only and path-parameterized, like the rest of the core.

import json
import os
import re
from datetime import datetime, timedelta, timezone

VERSION = 1


def normalize_title(title: str) -> str:
    """Canonical form used to decide two results are the same paper — also
    used by search.deduplicate for within-run duplicates."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def load(path: str) -> dict:
    """Read a history file; a missing or unreadable file yields an empty
    history (a corrupt file must cost repeats, not the weekly digest)."""
    try:
        with open(path, encoding="utf-8") as f:
            hist = json.load(f)
        if isinstance(hist.get("entries"), dict):
            return hist
        print(f"  [history] {path} has no entries dict — starting fresh")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  [history] Could not read {path} ({e}) — starting fresh")
    return {"version": VERSION, "entries": {}}


def filter_unseen(papers: list[dict], hist: dict) -> tuple[list[dict], list[dict]]:
    """Split papers into (unseen, already_listed). A paper matches history by
    normalized title or, failing that, by exact URL — titles occasionally get
    edited between a preprint and the journal version."""
    entries = hist["entries"]
    urls = {e["url"] for e in entries.values() if e.get("url")}
    unseen, seen = [], []
    for p in papers:
        key = normalize_title(p.get("title", ""))
        if (key and key in entries) or (p.get("url") and p["url"] in urls):
            seen.append(p)
        else:
            unseen.append(p)
    return unseen, seen


def record(hist: dict, papers: list[dict], run_date: str) -> int:
    """Add papers to history, keyed by normalized title. Returns how many were
    new; papers already present keep their original first_listed date."""
    added = 0
    for p in papers:
        key = normalize_title(p.get("title", ""))
        if not key or key in hist["entries"]:
            continue
        hist["entries"][key] = {
            "title": p.get("title", ""),
            "url": p.get("url", ""),
            "first_listed": run_date,
        }
        added += 1
    return added


def prune(hist: dict, retention_days: int, *, today: str | None = None) -> int:
    """Drop entries first listed more than retention_days ago (0 = keep
    forever). Old entries can't recur anyway — even PubMed's year-only dates
    stop matching once the search window leaves their publication year."""
    if retention_days <= 0:
        return 0
    if today is None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = (datetime.strptime(today, "%Y-%m-%d")
              - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    stale = [k for k, e in hist["entries"].items()
             if e.get("first_listed", "") < cutoff]
    for k in stale:
        del hist["entries"][k]
    return len(stale)


def save(hist: dict, path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
        f.write("\n")
