# Tests for history.py — the cross-run memory of already-listed papers.

import history


def _paper(title, url=""):
    return {"title": title, "url": url}


def test_normalize_title_strips_case_and_punctuation():
    assert (history.normalize_title("Combining Observational Studies, to Reduce Biases!")
            == history.normalize_title("combining observational studies to reduce biases"))


def test_load_missing_file_yields_empty_history(tmp_path):
    assert history.load(str(tmp_path / "_seen.json")) == {"version": 1, "entries": {}}


def test_load_corrupt_file_yields_empty_history(tmp_path):
    p = tmp_path / "_seen.json"
    p.write_text("{not json")
    assert history.load(str(p))["entries"] == {}
    p.write_text('{"entries": [1, 2]}')  # wrong shape
    assert history.load(str(p))["entries"] == {}


def test_record_save_load_round_trip(tmp_path):
    path = str(tmp_path / "_seen.json")
    hist = history.load(path)
    # The second paper is a same-title duplicate and must not double-record.
    assert history.record(hist, [_paper("A Paper", "http://x"),
                                 _paper("A paper.")], "2026-09-06") == 1
    history.save(hist, path)
    entry = next(iter(history.load(path)["entries"].values()))
    assert entry == {"title": "A Paper", "url": "http://x",
                     "first_listed": "2026-09-06"}


def test_record_keeps_first_listed_date():
    hist = {"version": 1, "entries": {}}
    history.record(hist, [_paper("A Paper")], "2026-08-23")
    assert history.record(hist, [_paper("a paper!")], "2026-09-06") == 0
    assert next(iter(hist["entries"].values()))["first_listed"] == "2026-08-23"


def test_filter_unseen_matches_by_title_or_url():
    hist = {"version": 1, "entries": {}}
    history.record(hist, [_paper("Old Paper", "http://old")], "2026-08-23")
    papers = [
        _paper("Old Paper!", "http://elsewhere"),      # title match
        _paper("Renamed After Review", "http://old"),  # URL match
        _paper("Brand New", "http://new"),
    ]
    unseen, seen = history.filter_unseen(papers, hist)
    assert [p["title"] for p in unseen] == ["Brand New"]
    assert [p["title"] for p in seen] == ["Old Paper!", "Renamed After Review"]


def test_untitled_papers_are_never_recorded_or_matched():
    hist = {"version": 1, "entries": {}}
    assert history.record(hist, [_paper("")], "2026-08-23") == 0
    unseen, seen = history.filter_unseen([_paper("")], hist)
    assert len(unseen) == 1 and not seen


def test_prune_drops_only_stale_entries():
    hist = {"version": 1, "entries": {}}
    history.record(hist, [_paper("Old")], "2024-01-01")
    history.record(hist, [_paper("Recent")], "2026-09-01")
    assert history.prune(hist, 730, today="2026-09-06") == 1
    assert [e["title"] for e in hist["entries"].values()] == ["Recent"]


def test_prune_zero_retention_keeps_forever():
    hist = {"version": 1, "entries": {}}
    history.record(hist, [_paper("Ancient")], "1999-01-01")
    assert history.prune(hist, 0, today="2026-09-06") == 0
    assert len(hist["entries"]) == 1
