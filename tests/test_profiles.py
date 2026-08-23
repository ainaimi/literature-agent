# Tests for profiles.py — cache behavior with tmp_path, LLM stubbed.

import json
from datetime import datetime, timedelta, timezone

import profiles


def _write_cache(path, profile="cached profile", folder_hash="h", age_days=0):
    generated = datetime.now(timezone.utc) - timedelta(days=age_days)
    path.write_text(json.dumps({
        "generated_at": generated.isoformat(),
        "folder_hash": folder_hash,
        "profile": profile,
    }))


def _no_llm(prompt, system=""):
    raise AssertionError("llm_call must not be invoked on this path")


def test_fresh_cache_hit_no_llm(tmp_path, capsys):
    interests = tmp_path / "interests"
    interests.mkdir()
    (interests / "note.md").write_text("methods methods methods")
    cache_file = tmp_path / "cache.json"
    _write_cache(cache_file, folder_hash=profiles._folder_hash(interests))

    result = profiles.get_profile(interests_dir=str(interests),
                                  cache_file=str(cache_file),
                                  max_age_days=30, llm_call=_no_llm)
    assert result == "cached profile"
    assert "Using cached relevance profile." in capsys.readouterr().out


def test_stale_cache_regenerates_and_saves(tmp_path):
    interests = tmp_path / "interests"
    interests.mkdir()
    (interests / "note.md").write_text("causal inference text")
    cache_file = tmp_path / "cache.json"
    _write_cache(cache_file, folder_hash=profiles._folder_hash(interests),
                 age_days=31)  # past max_age_days=30

    calls = []

    def fake_llm(prompt, system=""):
        calls.append(prompt)
        return "fresh profile"

    result = profiles.get_profile(interests_dir=str(interests),
                                  cache_file=str(cache_file),
                                  max_age_days=30, llm_call=fake_llm)
    assert result == "fresh profile"
    assert len(calls) == 1
    assert "causal inference text" in calls[0]
    saved = json.loads(cache_file.read_text())
    assert saved["profile"] == "fresh profile"


def test_changed_files_regenerate(tmp_path):
    interests = tmp_path / "interests"
    interests.mkdir()
    (interests / "note.md").write_text("new content")
    cache_file = tmp_path / "cache.json"
    _write_cache(cache_file, folder_hash="stale-hash-of-old-files")

    result = profiles.get_profile(interests_dir=str(interests),
                                  cache_file=str(cache_file), max_age_days=30,
                                  llm_call=lambda p, system="": "regenerated")
    assert result == "regenerated"


def test_headless_fallback_uses_restored_cache(tmp_path, capsys):
    # The GitHub Actions path: no interests/ files, but a cache restored
    # from the PROFILE_CACHE_B64 secret. Age/hash must NOT matter here.
    cache_file = tmp_path / "cache.json"
    _write_cache(cache_file, profile="restored cloud profile",
                 folder_hash="irrelevant", age_days=400)

    result = profiles.get_profile(interests_dir=str(tmp_path / "missing"),
                                  cache_file=str(cache_file),
                                  max_age_days=30, llm_call=_no_llm)
    assert result == "restored cloud profile"
    assert "No interests/ files present; using restored cache." in capsys.readouterr().out


def test_headless_no_cache_topic_only(tmp_path):
    result = profiles.get_profile(interests_dir=str(tmp_path / "missing"),
                                  cache_file=str(tmp_path / "nocache.json"),
                                  max_age_days=30, llm_call=_no_llm)
    assert result == ("(No papers found in interests/ folder — "
                      "using topic-only relevance scoring.)")
