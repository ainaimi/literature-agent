#!/usr/bin/env python3
# run.py — CLI entry point for the literature agent
#
# Usage:
#   uv run python run.py            # full run: search → score → send
#   uv run python run.py --dry-run  # search and score, print digest, don't send
#   uv run python run.py --search-only  # search only, print titles, no LLM calls
#
# The pipeline itself lives in pipeline.run_for_user(); this file only parses
# arguments, loads the environment, and assembles settings + credentials from
# config.py (the single-user tuning file).

import argparse
import os
import sys

from dotenv import load_dotenv

import config
import pipeline
from models import PlatformCredentials, UserSettings


def main() -> int:
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

    pipeline.run_for_user(settings, creds,
                          dry_run=args.dry_run, search_only=args.search_only)
    # Every outcome (including empty search weeks) is a successful run —
    # the Sunday CI job must not report failure on a quiet week.
    return 0


if __name__ == "__main__":
    sys.exit(main())
