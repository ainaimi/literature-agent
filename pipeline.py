# pipeline.py — the framework-agnostic core: one full run for one user.
#
# run_for_user() is what a web app's worker (or the CLI in run.py) calls per
# tenant. It never touches config.py, os.environ, or sys.exit — everything
# arrives via UserSettings/PlatformCredentials, and every outcome is a
# RunResult status.

import json
import os
from datetime import datetime, timezone

import digest
import history
import llm
import profiles
import score
import search
import send
from models import PlatformCredentials, RunResult, UserSettings


def run_for_user(settings: UserSettings, credentials: PlatformCredentials, *,
                 dry_run: bool = False, search_only: bool = False,
                 include_seen: bool = False, log=print) -> RunResult:
    """Run the full profile → search → score → digest → send pipeline for one
    user. dry_run renders everything but writes a preview file instead of
    emailing; search_only stops after search (note: profile loading still runs
    first and may regenerate a stale cache via one LLM call, matching the
    historical CLI behavior); include_seen also lists papers that already
    appeared in a past digest, which are skipped by default."""
    log("=" * 60)
    log("Literature Agent")
    log("=" * 60)

    llm_call = llm.make_llm_call(settings, credentials)

    # Step 1: Load relevance profile
    log("\n[1/4] Loading researcher profile...")
    researcher_profile = profiles.get_profile(
        interests_dir=settings.interests_dir,
        cache_file=settings.profile_cache_file,
        max_age_days=settings.profile_max_age_days,
        llm_call=llm_call)
    log(f"  Profile: {researcher_profile[:120]}...")

    # Step 2: Search all databases
    log(f"\n[2/4] Searching {len(settings.databases)} databases "
        f"(last {settings.lookback_days} days)...")
    papers = search.fetch_all_papers(settings, credentials)

    run_date = datetime.now().strftime("%Y-%m-%d")

    # Drop papers already listed in a previously sent digest — the searches
    # re-return them for weeks when publication dates are vague, so the memory
    # lives here rather than in the per-database date filters.
    hist = history.load(settings.seen_path) if settings.skip_seen_papers else None
    skipped_seen = 0
    if hist is not None and not include_seen:
        papers, already_listed = history.filter_unseen(papers, hist)
        skipped_seen = len(already_listed)
        if skipped_seen:
            log(f"  Skipping {skipped_seen} papers already listed in past "
                f"digests → {len(papers)} new")

    if not papers:
        log("No new papers found. Exiting." if skipped_seen
            else "No papers found. Exiting.")
        return RunResult(status="no_papers", run_date=run_date,
                         skipped_seen=skipped_seen,
                         profile_text=researcher_profile)

    if search_only:
        log(f"\nFound {len(papers)} papers:")
        for i, p in enumerate(papers, 1):
            log(f"  {i:3}. [{p['source']}] {p['title'][:80]}")
        return RunResult(status="search_only", run_date=run_date,
                         total_searched=len(papers),
                         skipped_seen=skipped_seen,
                         profile_text=researcher_profile)

    # Step 3: Score and summarize
    log(f"\n[3/4] Scoring {len(papers)} papers with {settings.llm_provider}/{settings.llm_model}...")
    top_papers, all_scored = score.score_all(
        papers, researcher_profile,
        llm_call=llm_call,
        threshold=settings.relevance_threshold,
        top_n=settings.top_n_papers,
        persona=settings.persona,
        example_name=settings.example_name)
    passed_count = len(all_scored)

    if not top_papers:
        log("No papers passed the relevance threshold. Exiting.")
        return RunResult(status="no_passed", run_date=run_date,
                         total_searched=len(papers),
                         skipped_seen=skipped_seen,
                         profile_text=researcher_profile)

    # Persist the full scored set as structured data. This decouples data from
    # presentation (re-render the email/attachment without re-scoring) and is
    # the per-run record a future web app would store per user.
    record_path = persist_run(settings, papers, all_scored, passed_count,
                              run_date, log=log)

    # Step 4: Format and send
    log(f"\n[4/4] Formatting digest (top {len(top_papers)} of {passed_count} that passed)...")
    note = f"Full scored list ({passed_count} papers) attached as an HTML file."
    report         = digest.format_digest(top_papers, len(papers), passed_count,
                                          skipped_seen=skipped_seen)
    report_html    = digest.format_digest_html(top_papers, len(papers), passed_count,
                                                full_list_note=note,
                                                threshold=settings.relevance_threshold,
                                                skipped_seen=skipped_seen)
    full_list_html = digest.format_full_list_html(all_scored, len(papers),
                                                  threshold=settings.relevance_threshold,
                                                  skipped_seen=skipped_seen)

    log("\n" + "=" * 60)
    log(report)
    log("=" * 60)

    attachment_name = f"full-scored-list-{run_date}.html"

    result = RunResult(status="dry_run" if dry_run else "sent",
                       run_date=run_date,
                       total_searched=len(papers),
                       skipped_seen=skipped_seen,
                       passed_count=passed_count,
                       top_papers=top_papers,
                       all_scored=all_scored,
                       profile_text=researcher_profile,
                       digest_text=report,
                       digest_html=report_html,
                       full_list_html=full_list_html,
                       record_path=record_path)

    if dry_run:
        preview_path = settings.preview_path
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(full_list_html)
        result.preview_path = preview_path
        log("\n[dry-run] Digest printed above. Not sent.")
        log(f"[dry-run] Full scored list ({passed_count} papers) written to "
            f"{preview_path} — open it to preview the email attachment.")
    else:
        log(f"\nSending to {settings.email_to or 'recipient'}...")
        send.send_email(report_html, subject=settings.email_subject,
                        to_addr=settings.email_to, credentials=credentials,
                        attachment=(attachment_name, full_list_html))
        log("Sent.")
        if hist is not None:
            # Everything the user just received (digest + attachment) counts
            # as listed. Only a delivered digest is recorded — dry runs must
            # not hide papers from the real Sunday send.
            added = history.record(hist, all_scored, run_date)
            history.prune(hist, settings.seen_retention_days)
            history.save(hist, settings.seen_path)
            log(f"  History: {added} papers recorded → {settings.seen_path}")

    return result


def persist_run(settings: UserSettings, papers: list[dict],
                all_scored: list[dict], passed_count: int, run_date: str, *,
                log=print) -> str:
    """Write the full scored set to <data_dir>/_last_run.json (latest) and
    <data_dir>/_runs/<date>.json (dated archive). Both are gitignored — they
    hold scored reading data, and let a digest be re-rendered without paying
    to re-score. Returns the dated record path."""
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_date,
        "total_searched": len(papers),
        "passed_count": passed_count,
        "threshold": settings.relevance_threshold,
        "lookback_days": settings.lookback_days,
        "top_n": settings.top_n_papers,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "papers": all_scored,
    }
    payload = json.dumps(record, indent=2, ensure_ascii=False)
    if settings.data_dir != ".":
        os.makedirs(settings.data_dir, exist_ok=True)
    with open(settings.last_run_path, "w", encoding="utf-8") as f:
        f.write(payload)
    os.makedirs(settings.runs_dir, exist_ok=True)
    dated_path = os.path.join(settings.runs_dir, f"{run_date}.json")
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(payload)
    log(f"  Saved run data → {settings.last_run_path} and {dated_path}")
    return dated_path
