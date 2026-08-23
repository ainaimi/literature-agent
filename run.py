#!/usr/bin/env python3
# run.py — main entry point for the literature agent
#
# Usage:
#   uv run python run.py            # full run: search → score → send
#   uv run python run.py --dry-run  # search and score, print digest, don't send
#   uv run python run.py --search-only  # search only, print titles, no LLM calls

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

import config
import profiles
import search
import score
import digest
import send
import llm
from models import PlatformCredentials, UserSettings


def main():
    parser = argparse.ArgumentParser(description="Literature surveillance agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run everything but don't send the email")
    parser.add_argument("--search-only", action="store_true",
                        help="Search databases only, print titles, skip LLM and email")
    args = parser.parse_args()

    # The single place environment loading happens. Keep the explicit ~/.env
    # path — bare load_dotenv() would search the CWD instead. On CI there is
    # no ~/.env and secrets arrive as real env vars (dotenv never overrides).
    load_dotenv(os.path.expanduser("~/.env"))
    settings = UserSettings.from_config_module(config)
    creds = PlatformCredentials.from_env(
        s2_key_override=getattr(config, "SEMANTIC_SCHOLAR_API_KEY", ""))

    print("=" * 60)
    print("Literature Agent")
    print("=" * 60)

    llm_call = llm.make_llm_call(settings, creds)

    # Step 1: Load relevance profile
    print("\n[1/4] Loading researcher profile...")
    researcher_profile = profiles.get_profile(
        interests_dir=settings.interests_dir,
        cache_file=settings.profile_cache_file,
        max_age_days=settings.profile_max_age_days,
        llm_call=llm_call)
    print(f"  Profile: {researcher_profile[:120]}...")

    # Step 2: Search all databases
    print(f"\n[2/4] Searching {len(config.DATABASES)} databases "
          f"(last {config.LOOKBACK_DAYS} days)...")
    papers = search.fetch_all_papers()

    if not papers:
        print("No papers found. Exiting.")
        sys.exit(0)

    if args.search_only:
        print(f"\nFound {len(papers)} papers:")
        for i, p in enumerate(papers, 1):
            print(f"  {i:3}. [{p['source']}] {p['title'][:80]}")
        sys.exit(0)

    # Step 3: Score and summarize
    print(f"\n[3/4] Scoring {len(papers)} papers with {config.LLM_PROVIDER}/{config.LLM_MODEL}...")
    top_papers, all_scored = score.score_all(papers, researcher_profile)
    passed_count = len(all_scored)

    if not top_papers:
        print("No papers passed the relevance threshold. Exiting.")
        sys.exit(0)

    # Persist the full scored set as structured data. This decouples data from
    # presentation (re-render the email/attachment without re-scoring) and is the
    # per-run record a future web app would store per user.
    run_date = datetime.now().strftime("%Y-%m-%d")
    _persist_run(papers, all_scored, passed_count, run_date)

    # Step 4: Format and send
    print(f"\n[4/4] Formatting digest (top {len(top_papers)} of {passed_count} that passed)...")
    note = f"Full scored list ({passed_count} papers) attached as an HTML file."
    report         = digest.format_digest(top_papers, len(papers), passed_count)
    report_html    = digest.format_digest_html(top_papers, len(papers), passed_count,
                                                full_list_note=note,
                                                threshold=settings.relevance_threshold)
    full_list_html = digest.format_full_list_html(all_scored, len(papers),
                                                  threshold=settings.relevance_threshold)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    attachment_name = f"full-scored-list-{run_date}.html"

    if args.dry_run:
        preview_path = "_full-scored-list-preview.html"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(full_list_html)
        print("\n[dry-run] Digest printed above. Not sent.")
        print(f"[dry-run] Full scored list ({passed_count} papers) written to "
              f"{preview_path} — open it to preview the email attachment.")
    else:
        print(f"\nSending to {settings.email_to or 'recipient'}...")
        send.send_email(report_html, subject=settings.email_subject,
                        to_addr=settings.email_to, credentials=creds,
                        attachment=(attachment_name, full_list_html))
        print("Sent.")


def _persist_run(papers: list[dict], all_scored: list[dict],
                 passed_count: int, run_date: str):
    """Write the full scored set to _last_run.json (latest) and _runs/<date>.json
    (dated archive). Both are gitignored — they hold your scored reading data, and
    let you re-render a digest without paying to re-score."""
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_date,
        "total_searched": len(papers),
        "passed_count": passed_count,
        "threshold": config.RELEVANCE_THRESHOLD,
        "lookback_days": config.LOOKBACK_DAYS,
        "top_n": config.TOP_N_PAPERS,
        "provider": config.LLM_PROVIDER,
        "model": config.LLM_MODEL,
        "papers": all_scored,
    }
    payload = json.dumps(record, indent=2, ensure_ascii=False)
    with open("_last_run.json", "w", encoding="utf-8") as f:
        f.write(payload)
    os.makedirs("_runs", exist_ok=True)
    with open(os.path.join("_runs", f"{run_date}.json"), "w", encoding="utf-8") as f:
        f.write(payload)
    print(f"  Saved run data → _last_run.json and _runs/{run_date}.json")


if __name__ == "__main__":
    main()
