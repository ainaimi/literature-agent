# Literature Surveillance Agent

An automated pipeline that, once a week, searches **PubMed, arXiv, medRxiv, and
Semantic Scholar**, scores every new paper against *your* research profile with an
LLM, and emails you a ranked digest of the best ones — each with a short summary
and a one-line "why you should read this."

It is designed to run **unattended in the cloud** (via GitHub Actions) so the
digest arrives every Sunday morning whether or not your own computer is on. It
can also be run locally on demand.

```
 PubMed ┐
 arXiv  ├─▶ dedupe ─▶ keyword pre-filter ─▶ LLM relevance score ─▶ top-N digest ─▶ email
 medRxiv│                (fast, free)          (vs. your profile)
 S2     ┘
```

---

## Table of contents

1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Install](#1-install)
4. [Add your credentials (`~/.env`)](#2-add-your-credentials-env)
5. [Configure the agent (`config.py`)](#3-configure-the-agent-configpy)
6. [Add your papers (`interests/`)](#4-add-your-papers-interests)
7. [Test it locally](#5-test-it-locally)
8. [Schedule it — Option A: GitHub Actions (recommended, always-on)](#option-a-github-actions-recommended-always-on)
9. [Schedule it — Option B: local cron / launchd](#option-b-local-cron--launchd-runs-only-when-your-computer-is-on)
10. [Cost](#cost)
11. [Troubleshooting](#troubleshooting)
12. [File reference](#file-reference)

---

## How it works

1. **Search** each configured database using topic *clusters* you define, plus a
   list of *followed authors* whose new work always comes through.
2. **Pre-filter** results by keyword to drop obvious noise — fast and free, before
   any LLM is involved.
3. **Skip repeats.** Every paper listed in a sent digest is recorded in
   `_seen.json`; later runs drop those papers before scoring. (Databases
   re-return old papers for weeks when publication dates are vague — a
   year-only PubMed date matches every weekly window in that year.)
4. **Score** each remaining paper from 0–10 against a *researcher profile* the
   agent builds automatically from whatever PDFs / Word / LaTeX files you drop
   into `interests/`.
5. **Email** you the top *N* papers (you define *N*), formatted as an HTML digest,
   with the complete list of every paper that passed the threshold attached as an
   HTML file.

---

## Prerequisites

| You need | Why | Where to get it |
|----------|-----|-----------------|
| **Python 3.11+** | Runs the agent | Usually preinstalled; else [python.org](https://www.python.org) |
| **[`uv`](https://docs.astral.sh/uv/)** | Manages the environment & dependencies | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **An LLM API key** | Scores papers | [Anthropic](https://console.anthropic.com) or [OpenAI](https://platform.openai.com) should work fine. Or run a local [Ollama](https://ollama.com) model for free (not tested, likely lower quality). |
| **A Gmail App Password** | Sends the digest | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification; not your normal password) |
| **(For cloud runs) a GitHub account + [`gh` CLI](https://cli.github.com)** | Hosts the weekly schedule | `brew install gh` then `gh auth login` |
| *(optional)* An [NCBI API key](https://www.ncbi.nlm.nih.gov/account/) | Raises the PubMed rate limit | Free with an NCBI account |
| *(optional)* A [Semantic Scholar API key](https://www.semanticscholar.org/product/api) | Raises the S2 rate limit 6× | Free |

---

## 1. Install

```bash
git clone https://github.com/<your-username>/literature-agent.git
cd literature-agent
uv sync            # creates the virtual environment and installs dependencies
```

## 2. Add your credentials (`~/.env`)

Secrets live in a `~/.env` file in your home directory. This file should **never** be pushed to the repo
(the `.gitignore` keeps `.env` out of git). Copy the template and fill it in:

```bash
cp .env.example ~/.env
$EDITOR ~/.env
```

At minimum you need:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...        # or OPENAI_API_KEY, matching LLM_PROVIDER in config.py
SMTP_USERNAME=you@gmail.com         # the Gmail account that sends the digest
SMTP_PASSWORD=your-16-char-app-password
EMAIL_TO=you@institution.edu        # where the digest is delivered (can equal SMTP_USERNAME)
```

Optional keys (`NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `EMAIL_FROM`,
`SMTP_HOST`, `SMTP_PORT`) are documented in `.env.example`.

> The code reads these with `os.environ`, and `python-dotenv` loads `~/.env`
> **without overriding** variables already present in the environment. That is
> exactly why the same code runs unchanged in GitHub Actions — there the secrets
> are injected as real environment variables instead of a `~/.env` file.

## 3. Configure the agent (`config.py`)

`config.py` is the only file you edit to tune behavior. The main sections:

- **LLM provider** (top of file) — `anthropic` (default, `claude-haiku-4-5`),
  `openai`, or `ollama`, plus the model name.
- **`SEARCH_CLUSTERS`** — your research topics. Each key is a label; each value is
  a list of search strings. Replace the examples with your own.
- **`CLUSTER_DATABASES`** — optionally restrict a cluster to certain databases
  (e.g. keep clinical topics off arXiv).
- **`FOLLOWED_AUTHORS`** — researchers whose new papers always appear, regardless
  of score. Find a Semantic Scholar ID by opening the person's profile at
  [semanticscholar.org](https://www.semanticscholar.org) and copying the number
  at the end of the URL.
- **`EXCLUDE_KEYWORDS` / `REQUIRE_KEYWORDS`** — the cheapest lever for cutting
  noise (and cost), applied to titles before any LLM call.
- **Search settings** — `LOOKBACK_DAYS` (default 7), `RELEVANCE_THRESHOLD`
  (0–10, default 6), `TOP_N_PAPERS` (default 20).

## 4. Add your papers (`interests/`)

Drop representative PDFs, Word docs (`.docx`), LaTeX (`.tex`), or plain text
(`.txt` / `.md`) into `interests/`. On first run the agent reads them and asks the
LLM to write a 250–350 word **researcher profile**, cached in `_profile_cache.json`
and regenerated automatically when the folder's contents change (or after 30 days).

```bash
cp ~/Downloads/my-recent-paper.pdf interests/
cp ~/grants/aims.docx interests/
```

`interests/` and `_profile_cache.json` are **gitignored** — your papers stay
private and never get pushed. If the folder is empty the agent falls back to
topic-only scoring. (For cloud runs, see the profile note in Option A.)

## 5. Test it locally

Always dry-run before scheduling:

```bash
uv run python run.py --search-only   # just print what the searches return — no LLM, no email
uv run python run.py --dry-run       # full search + scoring, prints the digest, sends nothing
uv run python run.py                 # the real thing: search → score → email
uv run python run.py --include-seen  # one-off: also list papers from past digests
```

Only a *sent* digest records papers into `_seen.json` — dry runs never hide
papers from the real Sunday send.

Once `--dry-run` looks right and one real run lands in your inbox, you're ready to
automate.

---

## Schedule it

### Option A: GitHub Actions (recommended, always-on)

This runs the agent on GitHub's servers on a weekly cron, so the digest is sent
**even when your laptop is closed**. It's free for this workload.

**A1. Create the repository and push.** From inside the project folder:

```bash
git add .
git status         # sanity check: no .env, no interests/, no _profile_cache.json listed
git commit -m "Initial commit"
gh repo create literature-agent --public --source . --remote origin --push
```

> Public vs. private is up to you. Your `config.py` (topics + followed authors)
> and `_seen.json` (titles/links of papers your digests already listed) become
> visible in a public repo — fine for most people, since research interests
> aren't secret — but **never commit secrets**; those only ever live in
> `~/.env` locally and in GitHub Secrets (below). One caveat: GitHub
> **auto-disables scheduled workflows in a public repo after 60 days with no new
> commits** — GitHub emails you first, and one click re-enables it. A private repo
> has no such limit.

**A2. Add your secrets** (encrypted; masked in logs; never committed). Run these
from inside the repo — they read the values straight out of your `~/.env`:

```bash
for k in ANTHROPIC_API_KEY SMTP_USERNAME SMTP_PASSWORD EMAIL_TO NCBI_API_KEY; do
  printf '%s' "$(grep "^${k}=" ~/.env | cut -d= -f2-)" | gh secret set "$k"
done
```

**A3. (Recommended) Upload your researcher profile** so cloud scoring matches your
interests without ever putting your `interests/` PDFs on GitHub. This stores the
generated profile (built during your local test in step 5) as one more encrypted
secret; the workflow decodes it at runtime:

```bash
base64 -i _profile_cache.json | gh secret set PROFILE_CACHE_B64
```

If you skip this, cloud runs still work — they just fall back to topic-only
scoring.

**A4. Trigger a test run and confirm the email arrives:**

```bash
gh workflow run weekly-digest.yml
gh run watch                          # follow the live logs
```

That's it — from now on `.github/workflows/weekly-digest.yml` runs every Sunday.

After each sent digest, the workflow **commits the updated `_seen.json` back to
the repository** — the runner's filesystem is discarded, so this is how next
week's cloud run knows which papers were already listed. If you also run
locally, `git pull` before — and `git push` after — a real (non-dry) local run
so both sides share one history. A nice side effect: the weekly commit resets GitHub's 60-day
idle timer, so the schedule no longer gets auto-disabled in a public repo.

**Changing the send time.** The workflow's cron is `17 12 * * 0` (Sundays, 12:17
UTC). GitHub cron is **always UTC and ignores daylight saving**, so in US Eastern
that is 8:17am in summer / 7:17am in winter. Edit the `cron:` line to shift it —
e.g. `17 13 * * 0` for an hour later — then commit and push.

### Option B: local cron / launchd (runs only when your computer is on)

If you'd rather not use the cloud, schedule it locally — but note the digest is
**skipped on any Sunday your machine is asleep or off.**

```bash
crontab -e
```

Add (adjust the paths — find `uv` with `which uv`):

```
0 8 * * 0 cd /path/to/literature-agent && /path/to/uv run python run.py >> _run.log 2>&1
```

**macOS note:** if the job fails silently, grant Full Disk Access to `/usr/sbin/cron`
under **System Settings → Privacy & Security → Full Disk Access**. This is required
when the project lives in Dropbox or another synced/protected folder. For a job
that can wake the Mac to run, use `launchd` with a `StartCalendarInterval` agent
instead of `cron`.

---

## Running from a settings file (multi-user core)

The pipeline is decoupled from `config.py`: all per-user settings can live in a
JSON file instead, which is how the future multi-user service will drive it
(one settings record per user). Credentials always come from the environment.

```bash
# Export the current config.py as JSON — a starting point for a tenant file:
uv run python run.py --print-settings > me.json

# Run any settings file (edit clusters, threshold, email_to, data_dir...):
uv run python run.py --settings me.json --dry-run
```

Setting `"data_dir"` in the JSON scopes that tenant's artifacts
(`_last_run.json`, `_runs/`, `_seen.json`, the dry-run preview) to that directory; the
interests folder and profile cache default to living under it too. Tip: when
cloning a tenant from an existing setup, copy its `_profile_cache.json` into
the tenant's cache path — otherwise the first run pays one LLM call to
regenerate the profile.

---

## Cost

With Claude Haiku (the default): roughly **$0.50–0.90 per weekly run**, depending
on how many papers survive the keyword pre-filter. Tighten `EXCLUDE_KEYWORDS` /
`REQUIRE_KEYWORDS` or lower `FETCH_LIMIT_PER_QUERY` to reduce LLM calls. GitHub
Actions minutes for a weekly ~5-minute job are negligible (well within the free
tier). Local Ollama is free but slower and lower quality.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `ValueError: SMTP_USERNAME / SMTP_PASSWORD not set` (or similar) | That key is missing from `~/.env` (local) or from GitHub Secrets (cloud). |
| Email never arrives | Using your Gmail password instead of an **App Password**; or 2-Step Verification isn't enabled on the account. |
| Scoring feels generic in the cloud | You didn't upload `PROFILE_CACHE_B64` (step A3), so it's using topic-only scoring. |
| "No papers found" | `LOOKBACK_DAYS` too small, or `REQUIRE_KEYWORDS` too aggressive. |
| "No new papers found" | Everything the searches returned was already listed in a past digest — a quiet week, not an error. |
| A paper you expected never appears | It was probably listed in an earlier digest (check `_seen.json`). Delete its entry to let it back in, or run `--include-seen` once. Delete the whole file to reset the history. |
| Same paper in several weekly digests | Should no longer happen — that's what `_seen.json` prevents (`SKIP_SEEN_PAPERS` in `config.py`). If it recurs, check that the workflow's "Persist the seen-papers history" step is pushing successfully. |
| Weekly runs stopped (public repo) | GitHub disabled the schedule after 60 days idle — re-enable it from the repo's **Actions** tab, or push any commit. |
| Digest arrives an hour off twice a year | Expected — GitHub cron is UTC and doesn't shift for daylight saving. |

---

## File reference

| File | Role |
|------|------|
| `config.py` | All user settings — the file you edit |
| `run.py` | CLI entry point (`--dry-run`, `--search-only`, `--settings`, `--print-settings`) |
| `models.py` | `UserSettings` / `PlatformCredentials` / `RunResult` data contracts |
| `pipeline.py` | `run_for_user(settings, credentials)` — the full pipeline for one user |
| `search.py` | Queries PubMed / arXiv / medRxiv / Semantic Scholar, deduplicates |
| `history.py` | Cross-run memory of already-listed papers (`_seen.json`) |
| `score.py` | Concurrent LLM scoring via `ThreadPoolExecutor` |
| `digest.py` | Formats the plain-text and HTML digest |
| `send.py` | SMTP email delivery |
| `profiles.py` | Builds the researcher profile from `interests/`; cached in `_profile_cache.json` |
| `llm.py` | Provider-agnostic wrapper (Anthropic / OpenAI / Ollama) |
| `tests/` | Unit tests (`uv run pytest`) — no network or LLM calls |
| `interests/` | Drop your papers here (gitignored — personal to each user) |
| `_last_run.json` / `_runs/` | Structured record of each run's full scored set (gitignored); re-render a digest without re-scoring |
| `_seen.json` | Papers already listed in a sent digest — **committed**, so cloud runs remember week to week |
| `.github/workflows/weekly-digest.yml` | The GitHub Actions schedule (Option A) |
| `.env.example` | Template for your `~/.env` credentials file |
