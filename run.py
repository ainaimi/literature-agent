#!/usr/bin/env python3
# run.py — main entry point for the literature agent
#
# Usage:
#   uv run python run.py            # full run: search → score → send
#   uv run python run.py --dry-run  # search and score, print digest, don't send
#   uv run python run.py --search-only  # search only, print titles, no LLM calls

import argparse
import os
import sys

import config
import profile
import search
import score
import digest
import send


def main():
    parser = argparse.ArgumentParser(description="Literature surveillance agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run everything but don't send the email")
    parser.add_argument("--search-only", action="store_true",
                        help="Search databases only, print titles, skip LLM and email")
    args = parser.parse_args()

    print("=" * 60)
    print("Literature Agent")
    print("=" * 60)

    # Step 1: Load relevance profile
    print("\n[1/4] Loading researcher profile...")
    researcher_profile = profile.get_profile()
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
    top_papers, passed_count = score.score_all(papers, researcher_profile)

    if not top_papers:
        print("No papers passed the relevance threshold. Exiting.")
        sys.exit(0)

    # Step 4: Format and send
    print(f"\n[4/4] Formatting digest ({len(top_papers)} papers)...")
    report      = digest.format_digest(top_papers, len(papers), passed_count)
    report_html = digest.format_digest_html(top_papers, len(papers), passed_count)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    if args.dry_run:
        print("\n[dry-run] Digest printed above. Not sent.")
    else:
        print(f"\nSending to {os.environ.get('EMAIL_TO', 'recipient')}...")
        send.send_email(report_html)
        print("Sent.")


if __name__ == "__main__":
    main()
