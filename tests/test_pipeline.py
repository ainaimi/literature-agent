# Tests for pipeline.py — persist_run schema/paths and run_for_user statuses,
# with the search/score/send stages stubbed (no network, no LLM).

import json

import pipeline
from models import PlatformCredentials, UserSettings

# The exact top-level key order of the historical run record
# (run.py's _persist_run before the extraction).
RECORD_KEYS = ["generated_at", "date", "total_searched", "passed_count",
               "threshold", "lookback_days", "top_n", "provider", "model",
               "papers"]

SCORED = [{"title": "P1", "score": 9}, {"title": "P2", "score": 7}]


def test_persist_run_writes_both_files_with_exact_schema(tmp_path):
    settings = UserSettings(data_dir=str(tmp_path))
    dated = pipeline.persist_run(settings, [{}, {}, {}], SCORED, 2,
                                 "2026-08-23", log=lambda *_: None)
    assert dated == str(tmp_path / "_runs" / "2026-08-23.json")
    latest = json.loads((tmp_path / "_last_run.json").read_text())
    archived = json.loads((tmp_path / "_runs" / "2026-08-23.json").read_text())
    assert latest == archived
    assert list(latest.keys()) == RECORD_KEYS
    assert latest["total_searched"] == 3
    assert latest["passed_count"] == 2
    assert latest["threshold"] == 6
    assert latest["papers"] == SCORED


def _stub_settings(tmp_path):
    return UserSettings(data_dir=str(tmp_path),
                        interests_dir=str(tmp_path / "no-interests"),
                        profile_cache_file=str(tmp_path / "no-cache.json"),
                        email_to="reader@uni.edu")


def test_run_for_user_no_papers_status(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.search, "fetch_all_papers",
                        lambda settings, creds: [])
    result = pipeline.run_for_user(_stub_settings(tmp_path),
                                   PlatformCredentials(), log=lambda *_: None)
    assert result.status == "no_papers"
    assert not (tmp_path / "_last_run.json").exists()


def test_run_for_user_search_only_skips_scoring(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.search, "fetch_all_papers",
                        lambda settings, creds: [
                            {"title": "T", "source": "pubmed"}])

    def no_score(*a, **k):
        raise AssertionError("score_all must not run under search_only")
    monkeypatch.setattr(pipeline.score, "score_all", no_score)

    result = pipeline.run_for_user(_stub_settings(tmp_path),
                                   PlatformCredentials(), search_only=True,
                                   log=lambda *_: None)
    assert result.status == "search_only"
    assert result.total_searched == 1


def test_run_for_user_dry_run_writes_preview_not_email(tmp_path, monkeypatch):
    papers = [{"title": "T", "abstract": "A", "source": "pubmed",
               "authors": "X", "year": 2026, "url": "u", "cluster": "c"}]
    monkeypatch.setattr(pipeline.search, "fetch_all_papers",
                        lambda settings, creds: list(papers))
    monkeypatch.setattr(pipeline.score, "score_all",
                        lambda *a, **k: ([dict(papers[0], score=8)],
                                         [dict(papers[0], score=8)]))

    def no_send(*a, **k):
        raise AssertionError("send_email must not run under dry_run")
    monkeypatch.setattr(pipeline.send, "send_email", no_send)

    result = pipeline.run_for_user(_stub_settings(tmp_path),
                                   PlatformCredentials(), dry_run=True,
                                   log=lambda *_: None)
    assert result.status == "dry_run"
    assert (tmp_path / "_full-scored-list-preview.html").exists()
    assert (tmp_path / "_last_run.json").exists()
    assert result.record_path == str(tmp_path / "_runs" / f"{result.run_date}.json")


def test_run_for_user_sent_status_calls_send(tmp_path, monkeypatch):
    papers = [{"title": "T", "abstract": "A", "source": "pubmed",
               "authors": "X", "year": 2026, "url": "u", "cluster": "c"}]
    scored = [dict(papers[0], score=8, summary_bullets=[], read_bullets=[])]
    monkeypatch.setattr(pipeline.search, "fetch_all_papers",
                        lambda settings, creds: list(papers))
    monkeypatch.setattr(pipeline.score, "score_all",
                        lambda *a, **k: (scored, scored))
    sent = {}

    def fake_send(html, *, subject, to_addr, credentials, attachment=None):
        sent.update(subject=subject, to_addr=to_addr, attachment=attachment[0])
    monkeypatch.setattr(pipeline.send, "send_email", fake_send)

    result = pipeline.run_for_user(_stub_settings(tmp_path),
                                   PlatformCredentials(), log=lambda *_: None)
    assert result.status == "sent"
    assert sent["to_addr"] == "reader@uni.edu"
    assert sent["subject"] == "Your Lit-Search Digest"
    assert sent["attachment"] == f"full-scored-list-{result.run_date}.html"


# ─── Cross-run history (papers listed once are never listed again) ───────────

PAPERS = [{"title": "T", "abstract": "A", "source": "pubmed",
           "authors": "X", "year": 2026, "url": "u", "cluster": "c"}]
SCORED_PAPERS = [dict(PAPERS[0], score=8, summary_bullets=[], read_bullets=[])]


def _stub_stages(monkeypatch, send=lambda *a, **k: None):
    monkeypatch.setattr(pipeline.search, "fetch_all_papers",
                        lambda settings, creds: [dict(p) for p in PAPERS])
    monkeypatch.setattr(pipeline.score, "score_all",
                        lambda *a, **k: (list(SCORED_PAPERS), list(SCORED_PAPERS)))
    monkeypatch.setattr(pipeline.send, "send_email", send)


def test_sent_run_records_history_and_next_run_skips(tmp_path, monkeypatch):
    _stub_stages(monkeypatch)
    settings = _stub_settings(tmp_path)

    first = pipeline.run_for_user(settings, PlatformCredentials(),
                                  log=lambda *_: None)
    assert first.status == "sent"
    assert first.skipped_seen == 0
    seen = json.loads((tmp_path / "_seen.json").read_text())
    assert [e["title"] for e in seen["entries"].values()] == ["T"]

    def no_score(*a, **k):
        raise AssertionError("previously listed papers must not be re-scored")
    monkeypatch.setattr(pipeline.score, "score_all", no_score)

    second = pipeline.run_for_user(settings, PlatformCredentials(),
                                   log=lambda *_: None)
    assert second.status == "no_papers"
    assert second.skipped_seen == 1


def test_dry_run_does_not_record_history(tmp_path, monkeypatch):
    _stub_stages(monkeypatch)
    result = pipeline.run_for_user(_stub_settings(tmp_path),
                                   PlatformCredentials(), dry_run=True,
                                   log=lambda *_: None)
    assert result.status == "dry_run"
    assert not (tmp_path / "_seen.json").exists()


def test_include_seen_lists_previously_recorded_papers(tmp_path, monkeypatch):
    _stub_stages(monkeypatch)
    settings = _stub_settings(tmp_path)
    pipeline.run_for_user(settings, PlatformCredentials(), log=lambda *_: None)

    again = pipeline.run_for_user(settings, PlatformCredentials(),
                                  include_seen=True, log=lambda *_: None)
    assert again.status == "sent"
    assert again.skipped_seen == 0


def test_skip_seen_papers_false_disables_history(tmp_path, monkeypatch):
    _stub_stages(monkeypatch)
    settings = UserSettings(data_dir=str(tmp_path),
                            interests_dir=str(tmp_path / "no-interests"),
                            profile_cache_file=str(tmp_path / "no-cache.json"),
                            skip_seen_papers=False)
    result = pipeline.run_for_user(settings, PlatformCredentials(),
                                   log=lambda *_: None)
    assert result.status == "sent"
    assert not (tmp_path / "_seen.json").exists()
