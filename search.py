# search.py — queries PubMed, arXiv, medRxiv, and Semantic Scholar

import re
import time
import requests
from datetime import datetime, timedelta, timezone

# Shared paper schema:
# {
#   "title":    str,
#   "abstract": str,
#   "authors":  str,          # "Last FM, Last FM, ..."
#   "year":     int | None,
#   "date":     str | None,   # ISO 8601 if available
#   "source":   str,          # "pubmed" | "arxiv" | "medrxiv" | "semantic_scholar"
#   "url":      str,
#   "cluster":  str | None,   # which search cluster triggered this result
# }


def _cutoff_date(lookback_days: int) -> str:
    d = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return d.strftime("%Y/%m/%d")


def _cutoff_iso(lookback_days: int) -> str:
    d = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return d.strftime("%Y-%m-%d")


def _cluster_uses(cluster_name: str, db: str, *,
                  cluster_databases: dict, databases: list) -> bool:
    """Check whether a cluster should query a given database."""
    if cluster_name in cluster_databases:
        return db in cluster_databases[cluster_name]
    return db in databases


# ─── PubMed ──────────────────────────────────────────────────────────────────

def _search_pubmed_query(query: str, limit: int, *, lookback_days: int,
                         api_key: str) -> list[dict]:
    cutoff = _cutoff_date(lookback_days)
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    search_params = {
        "db": "pubmed",
        "term": (
            f"({query})"
            f" AND (\"{cutoff}\"[Date - Publication] : \"3000\"[Date - Publication])"
            f" AND English[Language]"
        ),
        "retmax": limit,
        "retmode": "json",
        "sort": "date",
    }
    if api_key:
        search_params["api_key"] = api_key

    try:
        r = requests.get(f"{base}/esearch.fcgi", params=search_params, timeout=15)
        r.raise_for_status()
        pmids = r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"  [pubmed] Search error for '{query}': {e}")
        return []

    if not pmids:
        return []

    time.sleep(0.11 if api_key else 0.4)  # 10 req/s with key, 3 req/s without
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if api_key:
        fetch_params["api_key"] = api_key

    try:
        r = requests.get(f"{base}/efetch.fcgi", params=fetch_params, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  [pubmed] Fetch error: {e}")
        return []

    return _parse_pubmed_xml(r.text)


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    import xml.etree.ElementTree as ET
    papers = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    for article in root.findall(".//PubmedArticle"):
        try:
            title = article.findtext(".//ArticleTitle") or ""
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join((p.text or "") for p in abstract_parts if p.text)
            authors = []
            for author in article.findall(".//Author"):
                last = author.findtext("LastName") or ""
                initials = author.findtext("Initials") or ""
                if last:
                    authors.append(f"{last} {initials}".strip())
            pmid = article.findtext(".//PMID") or ""
            year_text = article.findtext(".//PubDate/Year")
            year = int(year_text) if year_text and year_text.isdigit() else None

            papers.append({
                "title": title.strip(),
                "abstract": abstract.strip(),
                "authors": ", ".join(authors[:5]),
                "year": year,
                "date": None,
                "source": "pubmed",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "cluster": None,
            })
        except Exception:
            continue

    return papers


def search_pubmed(settings, *, api_key: str) -> list[dict]:
    results = []
    for cluster_name, queries in settings.search_clusters.items():
        if not _cluster_uses(cluster_name, "pubmed",
                             cluster_databases=settings.cluster_databases,
                             databases=settings.databases):
            continue
        for query in queries:
            papers = _search_pubmed_query(query, settings.fetch_limit_per_query,
                                          lookback_days=settings.lookback_days,
                                          api_key=api_key)
            for p in papers:
                p["cluster"] = cluster_name
            results.extend(papers)
            time.sleep(0.4)
    return results


def search_pubmed_author(pubmed_query: str, limit: int, *, lookback_days: int,
                         api_key: str) -> list[dict]:
    papers = _search_pubmed_query(f"{pubmed_query}[Author]", limit,
                                  lookback_days=lookback_days, api_key=api_key)
    for p in papers:
        p["cluster"] = "followed_author"
    return papers


# ─── arXiv ───────────────────────────────────────────────────────────────────

def search_arxiv(settings) -> list[dict]:
    import xml.etree.ElementTree as ET
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.lookback_days)
    base = "http://export.arxiv.org/api/query"
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results = []

    # Build category filter string: "(cat:stat.ME OR cat:stat.AP OR ...)"
    categories = settings.arxiv_categories
    cat_filter = " OR ".join(f"cat:{c}" for c in categories) if categories else ""

    for cluster_name, queries in settings.search_clusters.items():
        if not _cluster_uses(cluster_name, "arxiv",
                             cluster_databases=settings.cluster_databases,
                             databases=settings.databases):
            continue
        for query in queries:
            search_q = f"all:{query}"
            if cat_filter:
                search_q = f"({search_q}) AND ({cat_filter})"

            params = {
                "search_query": search_q,
                "start": 0,
                "max_results": settings.fetch_limit_per_query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            try:
                r = requests.get(base, params=params, timeout=30)
                if r.status_code == 429:
                    print(f"  [arxiv] Rate limited on '{query}' — skipping")
                    time.sleep(5.0)
                    continue
                r.raise_for_status()
                root = ET.fromstring(r.text)
            except requests.exceptions.Timeout:
                print(f"  [arxiv] Timeout on '{query}' — skipping")
                continue
            except Exception as e:
                print(f"  [arxiv] Error for '{query}': {e}")
                continue

            for entry in root.findall("atom:entry", ns):
                published_str = entry.findtext("atom:published", namespaces=ns) or ""
                try:
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    if published < cutoff.replace(tzinfo=timezone.utc):
                        continue
                except Exception:
                    pass

                title = (entry.findtext("atom:title", namespaces=ns) or "").replace("\n", " ").strip()
                abstract = (entry.findtext("atom:summary", namespaces=ns) or "").replace("\n", " ").strip()
                authors = [
                    a.findtext("atom:name", namespaces=ns) or ""
                    for a in entry.findall("atom:author", ns)
                ]
                url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("type") == "text/html":
                        url = link.get("href", "")
                        break
                year = int(published_str[:4]) if published_str else None

                results.append({
                    "title": title,
                    "abstract": abstract,
                    "authors": ", ".join(authors[:5]),
                    "year": year,
                    "date": published_str[:10],
                    "source": "arxiv",
                    "url": url,
                    "cluster": cluster_name,
                })

            time.sleep(3.0)  # arXiv asks for 3s between requests

    return results


# ─── medRxiv ─────────────────────────────────────────────────────────────────

def search_medrxiv(settings) -> list[dict]:
    cutoff = _cutoff_iso(settings.lookback_days)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = "https://api.biorxiv.org/details/medrxiv"
    results = []

    # Build keyword sets only for clusters that should use medRxiv
    all_keywords = {
        cluster: [q.lower() for q in queries]
        for cluster, queries in settings.search_clusters.items()
        if _cluster_uses(cluster, "medrxiv",
                         cluster_databases=settings.cluster_databases,
                         databases=settings.databases)
    }
    if not all_keywords:
        return []

    try:
        url = f"{base}/{cutoff}/{today}/0/json"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json().get("collection", [])
    except Exception as e:
        print(f"  [medrxiv] Error: {e}")
        return []

    for paper in data:
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        text = title + " " + abstract

        matched_cluster = None
        for cluster_name, keywords in all_keywords.items():
            if any(kw in text for kw in keywords):
                matched_cluster = cluster_name
                break

        if matched_cluster:
            results.append({
                "title": paper.get("title", ""),
                "abstract": paper.get("abstract", ""),
                "authors": paper.get("authors", ""),
                "year": int(paper.get("date", "0000")[:4]),
                "date": paper.get("date"),
                "source": "medrxiv",
                "url": f"https://www.medrxiv.org/content/{paper.get('doi', '')}",
                "cluster": matched_cluster,
            })

    return results[:settings.fetch_limit_per_query * len(all_keywords)]


# ─── Semantic Scholar ────────────────────────────────────────────────────────

def _s2_headers(api_key: str) -> dict:
    return {"x-api-key": api_key} if api_key else {}


def _s2_request(url: str, params: dict, *, api_key: str,
                retries: int = 3) -> dict | None:
    """GET with exponential backoff on 429."""
    headers = _s2_headers(api_key)
    delay = 2.0
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code == 429:
                wait = delay * (2 ** attempt)
                print(f"  [s2] Rate limited — waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.HTTPError:
            return None
        except Exception as e:
            print(f"  [s2] Request error: {e}")
            return None
    return None


def _s2_paper_to_dict(paper: dict, cluster: str) -> dict | None:
    abstract = paper.get("abstract") or ""
    # Drop papers with no abstract or non-ASCII-dominant text (non-English)
    if not abstract.strip():
        return None
    ascii_ratio = sum(c.isascii() for c in abstract) / max(len(abstract), 1)
    if ascii_ratio < 0.85:
        return None

    authors = [a.get("name", "") for a in paper.get("authors", [])]
    url = paper.get("url") or ""
    if not url:
        ext = paper.get("externalIds") or {}
        doi = ext.get("DOI")
        pmid = ext.get("PubMed")
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return {
        "title": paper.get("title", ""),
        "abstract": abstract,
        "authors": ", ".join(authors[:5]),
        "year": paper.get("year"),
        "date": paper.get("publicationDate"),
        "source": "semantic_scholar",
        "url": url,
        "cluster": cluster,
    }


def _search_s2_query(query: str, limit: int, *, lookback_days: int,
                     api_key: str) -> list[dict]:
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,authors,year,publicationDate,externalIds,url",
        "publicationDateOrYear": f"{_cutoff_iso(lookback_days)}:",
    }
    data = _s2_request(
        "https://api.semanticscholar.org/graph/v1/paper/search", params,
        api_key=api_key,
    )
    return (data or {}).get("data", [])


def search_semantic_scholar(settings, *, api_key: str) -> list[dict]:
    if not api_key:
        print("  [s2] No API key found — skipping Semantic Scholar.")
        print("       Get a free key at semanticscholar.org/product/api")
        print("       Then add SEMANTIC_SCHOLAR_API_KEY=... to ~/.env")
        return []

    results = []
    delay = 1.5  # with API key: 100 req/5min = 1 req/3s; 1.5s is safe

    for cluster_name, queries in settings.search_clusters.items():
        if not _cluster_uses(cluster_name, "semantic_scholar",
                             cluster_databases=settings.cluster_databases,
                             databases=settings.databases):
            continue
        for query in queries:
            papers = _search_s2_query(query, settings.fetch_limit_per_query,
                                      lookback_days=settings.lookback_days,
                                      api_key=api_key)
            for p in papers:
                d = _s2_paper_to_dict(p, cluster_name)
                if d:
                    results.append(d)
            time.sleep(delay)

    return results


def search_s2_author(s2_author_id: str, limit: int, *, lookback_days: int,
                     api_key: str) -> list[dict]:
    cutoff = _cutoff_iso(lookback_days)
    params = {
        "limit": limit,
        "fields": "title,abstract,authors,year,publicationDate,externalIds,url",
    }
    data = _s2_request(
        f"https://api.semanticscholar.org/graph/v1/author/{s2_author_id}/papers",
        params,
        api_key=api_key,
    )
    if not data:
        return []

    results = []
    for p in (data.get("data") or []):
        pub_date = p.get("publicationDate") or ""
        if pub_date and pub_date < cutoff:
            continue
        d = _s2_paper_to_dict(p, "followed_author")
        if d:
            results.append(d)
    return results


# ─── Keyword pre-filtering ───────────────────────────────────────────────────

def apply_keyword_filters(papers: list[dict], *, exclude_keywords: list,
                          require_keywords: list) -> list[dict]:
    """
    Drop papers that match exclude_keywords or fail require_keywords.
    Matching is case-insensitive against the paper title.
    """
    excludes = [k.lower() for k in exclude_keywords]
    requires = [k.lower() for k in require_keywords]

    kept, dropped = [], 0
    for p in papers:
        title = p.get("title", "").lower()
        if excludes and any(kw in title for kw in excludes):
            dropped += 1
            continue
        if requires and not any(kw in title for kw in requires):
            dropped += 1
            continue
        kept.append(p)

    if dropped:
        print(f"[filter] Dropped {dropped} papers by keyword filter → {len(kept)} remain")
    return kept


# ─── Deduplication ───────────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def deduplicate(papers: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in papers:
        key = _normalize_title(p.get("title", ""))
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# ─── Main entry point ────────────────────────────────────────────────────────

def fetch_all_papers(settings, credentials) -> list[dict]:
    databases = settings.databases
    limit = settings.fetch_limit_per_query
    all_papers = []

    if "pubmed" in databases:
        print("[search] Querying PubMed...")
        all_papers.extend(search_pubmed(settings, api_key=credentials.ncbi_api_key))

    if "arxiv" in databases:
        print("[search] Querying arXiv...")
        all_papers.extend(search_arxiv(settings))

    if "medrxiv" in databases:
        print("[search] Querying medRxiv...")
        all_papers.extend(search_medrxiv(settings))

    if "semantic_scholar" in databases:
        print("[search] Querying Semantic Scholar...")
        all_papers.extend(search_semantic_scholar(settings,
                                                  api_key=credentials.s2_api_key))

    for author in settings.followed_authors:
        name = author.get("name", "unknown")
        s2_id = author.get("s2_author_id")
        pm_query = author.get("pubmed_query")

        if s2_id and "semantic_scholar" in databases:
            print(f"[search] Fetching papers by {name} (Semantic Scholar)...")
            all_papers.extend(search_s2_author(s2_id, limit,
                                               lookback_days=settings.lookback_days,
                                               api_key=credentials.s2_api_key))

        if pm_query and "pubmed" in databases:
            print(f"[search] Fetching papers by {name} (PubMed)...")
            all_papers.extend(search_pubmed_author(pm_query, limit,
                                                   lookback_days=settings.lookback_days,
                                                   api_key=credentials.ncbi_api_key))

    deduped = deduplicate(all_papers)
    print(f"[search] {len(all_papers)} total → {len(deduped)} after deduplication")
    filtered = apply_keyword_filters(deduped,
                                     exclude_keywords=settings.exclude_keywords,
                                     require_keywords=settings.require_keywords)
    return filtered
