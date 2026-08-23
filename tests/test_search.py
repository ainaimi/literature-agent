# Tests for search.py — pure logic only (no network).

import search


# ─── _cluster_uses ───────────────────────────────────────────────────────────

def test_cluster_uses_override_wins():
    assert search._cluster_uses(
        "methods", "arxiv",
        cluster_databases={"methods": ["arxiv"]},
        databases=["pubmed"])
    assert not search._cluster_uses(
        "methods", "pubmed",
        cluster_databases={"methods": ["arxiv"]},
        databases=["pubmed"])


def test_cluster_uses_falls_back_to_global_databases():
    assert search._cluster_uses(
        "clinical", "pubmed", cluster_databases={}, databases=["pubmed"])
    assert not search._cluster_uses(
        "clinical", "arxiv", cluster_databases={}, databases=["pubmed"])


# ─── apply_keyword_filters ───────────────────────────────────────────────────

PAPERS = [
    {"title": "Doubly robust estimation of treatment effects"},
    {"title": "Robotic surgery outcomes in knee osteoarthritis"},
    {"title": "TMLE for longitudinal data"},
]


def test_filters_passthrough_when_empty():
    assert search.apply_keyword_filters(
        PAPERS, exclude_keywords=[], require_keywords=[]) == PAPERS


def test_exclude_keywords_drop_matching_titles():
    kept = search.apply_keyword_filters(
        PAPERS, exclude_keywords=["Robotic Surgery"], require_keywords=[])
    assert [p["title"] for p in kept] == [
        "Doubly robust estimation of treatment effects",
        "TMLE for longitudinal data"]


def test_require_keywords_keep_only_matching_titles():
    kept = search.apply_keyword_filters(
        PAPERS, exclude_keywords=[], require_keywords=["robust", "tmle"])
    assert [p["title"] for p in kept] == [
        "Doubly robust estimation of treatment effects",
        "TMLE for longitudinal data"]


# ─── deduplicate ─────────────────────────────────────────────────────────────

def test_deduplicate_normalizes_titles():
    papers = [
        {"title": "Causal Inference: A Primer"},
        {"title": "causal inference — a primer"},   # same after normalization
        {"title": "Something else"},
        {"title": ""},                               # empty keys never kept
    ]
    unique = search.deduplicate(papers)
    assert [p["title"] for p in unique] == [
        "Causal Inference: A Primer", "Something else"]


# ─── _s2_paper_to_dict gates ─────────────────────────────────────────────────

def test_s2_paper_requires_abstract():
    assert search._s2_paper_to_dict({"title": "T", "abstract": ""}, "c") is None


def test_s2_paper_drops_non_ascii_dominant_abstracts():
    paper = {"title": "T", "abstract": "статья на русском языке о методах"}
    assert search._s2_paper_to_dict(paper, "c") is None


def test_s2_paper_builds_url_from_doi():
    paper = {"title": "T", "abstract": "An English abstract about methods.",
             "authors": [{"name": "A B"}], "year": 2026,
             "publicationDate": "2026-08-01",
             "externalIds": {"DOI": "10.1000/xyz"}}
    d = search._s2_paper_to_dict(paper, "methods")
    assert d["url"] == "https://doi.org/10.1000/xyz"
    assert d["cluster"] == "methods"
    assert d["source"] == "semantic_scholar"


# ─── _s2_headers ─────────────────────────────────────────────────────────────

def test_s2_headers():
    assert search._s2_headers("") == {}
    assert search._s2_headers("k") == {"x-api-key": "k"}
