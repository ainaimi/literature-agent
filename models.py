# models.py — the data contracts for the multi-tenant core.
#
# UserSettings is everything that varies per user (search agenda, thresholds,
# delivery). PlatformCredentials is everything the platform owns and shares
# across all users (LLM keys, SMTP account, database API keys) — kept separate
# so per-user data can round-trip through JSON/DB rows without ever touching
# secrets. This module must stay framework-agnostic: stdlib imports only,
# no config.py, no dotenv, no network.

import copy
import os
from collections.abc import Mapping
from dataclasses import MISSING, asdict, dataclass, field, fields

# The exact persona historically hardcoded in score.py's system prompt.
# UserSettings.persona defaults to it so existing digests keep today's voice.
DEFAULT_PERSONA = "a quantitative epidemiologist and statistician"

# config.py constant → UserSettings field. from_config_module consumes exactly
# these names; the test suite's parity guard checks every UPPERCASE name in
# config.py appears here (or is deliberately excluded), so a new tuning knob
# added to config.py can't be silently ignored.
CONFIG_FIELD_MAP = {
    "LLM_PROVIDER":          "llm_provider",
    "LLM_MODEL":             "llm_model",
    "DATABASES":             "databases",
    "CLUSTER_DATABASES":     "cluster_databases",
    "ARXIV_CATEGORIES":      "arxiv_categories",
    "SEARCH_CLUSTERS":       "search_clusters",
    "FOLLOWED_AUTHORS":      "followed_authors",
    "EXCLUDE_KEYWORDS":      "exclude_keywords",
    "REQUIRE_KEYWORDS":      "require_keywords",
    "LOOKBACK_DAYS":         "lookback_days",
    "FETCH_LIMIT_PER_QUERY": "fetch_limit_per_query",
    "RELEVANCE_THRESHOLD":   "relevance_threshold",
    "TOP_N_PAPERS":          "top_n_papers",
    "PERSONA":               "persona",        # optional in config.py
    "EXAMPLE_NAME":          "example_name",   # optional in config.py
    "INTERESTS_DIR":         "interests_dir",
    "PROFILE_CACHE_FILE":    "profile_cache_file",
    "PROFILE_MAX_AGE_DAYS":  "profile_max_age_days",
    "EMAIL_SUBJECT":         "email_subject",
}

# config.py names that intentionally have no UserSettings field:
# DIGEST_DAY / DIGEST_HOUR document the cron schedule (never read by code);
# SEMANTIC_SCHOLAR_API_KEY is a credential, routed through
# PlatformCredentials.from_env(s2_key_override=...) instead.
CONFIG_NAMES_NOT_MAPPED = {"DIGEST_DAY", "DIGEST_HOUR", "SEMANTIC_SCHOLAR_API_KEY"}


@dataclass(frozen=True)
class UserSettings:
    """Per-user configuration — the future per-tenant DB row."""

    # llm
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    # search
    databases: list = field(default_factory=lambda: [
        "pubmed", "arxiv", "medrxiv", "semantic_scholar"])
    cluster_databases: dict = field(default_factory=dict)
    arxiv_categories: list = field(default_factory=list)
    search_clusters: dict = field(default_factory=dict)
    followed_authors: list = field(default_factory=list)
    exclude_keywords: list = field(default_factory=list)
    require_keywords: list = field(default_factory=list)
    lookback_days: int = 7
    fetch_limit_per_query: int = 8
    relevance_threshold: int = 6
    top_n_papers: int = 20
    # scoring voice
    persona: str = DEFAULT_PERSONA
    example_name: str = "Naimi"
    # profile
    interests_dir: str = "./interests"
    profile_cache_file: str = "./_profile_cache.json"
    profile_max_age_days: int = 30
    # delivery
    email_subject: str = "Your Lit-Search Digest"
    email_to: str = ""
    # per-tenant filesystem root for run artifacts
    data_dir: str = "."

    @classmethod
    def from_config_module(cls, cfg, *, env: Mapping | None = None) -> "UserSettings":
        """Build settings from a config.py-style module plus the environment,
        reproducing the single-user tool's behavior exactly. Values are
        deep-copied so the frozen settings can't alias the live module's
        mutable constants. EMAIL_TO comes from env (it never lived in config)."""
        if env is None:
            env = os.environ
        defaults = {f.name: f for f in fields(cls)}
        kwargs = {}
        for config_name, field_name in CONFIG_FIELD_MAP.items():
            f = defaults[field_name]
            fallback = f.default_factory() if f.default is MISSING else f.default
            # getattr-with-default everywhere: config.py sections are
            # deletable today (search.py used getattr for several) — a user
            # who trims their config must get defaults, not AttributeError.
            kwargs[field_name] = copy.deepcopy(getattr(cfg, config_name, fallback))
        kwargs["email_to"] = env.get("EMAIL_TO", "")
        return cls(**kwargs)

    @classmethod
    def from_dict(cls, d: dict) -> "UserSettings":
        """Build settings from a plain dict (JSON tenant file / DB row).
        Unknown keys are an error — silent typos in a tenant file would
        otherwise become silent defaults. interests_dir/profile_cache_file
        default to living under data_dir when only data_dir is given."""
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"Unknown settings key(s): {sorted(unknown)}. "
                             f"Valid keys: {sorted(known)}")
        d = copy.deepcopy(dict(d))
        data_dir = d.get("data_dir")
        if data_dir and data_dir != ".":
            d.setdefault("interests_dir", os.path.normpath(
                os.path.join(data_dir, "interests")))
            d.setdefault("profile_cache_file", os.path.normpath(
                os.path.join(data_dir, "_profile_cache.json")))
        return cls(**d)

    def to_dict(self) -> dict:
        return asdict(self)

    # Derived artifact paths. normpath so the default data_dir="." yields the
    # literal historical paths ("_last_run.json", "_runs") — the GitHub Actions
    # artifact globs and the printed progress lines depend on them.
    @property
    def last_run_path(self) -> str:
        return os.path.normpath(os.path.join(self.data_dir, "_last_run.json"))

    @property
    def runs_dir(self) -> str:
        return os.path.normpath(os.path.join(self.data_dir, "_runs"))

    @property
    def preview_path(self) -> str:
        return os.path.normpath(os.path.join(self.data_dir,
                                             "_full-scored-list-preview.html"))


@dataclass(frozen=True)
class PlatformCredentials:
    """Platform-owned secrets shared by all users (no-BYOK model)."""

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ncbi_api_key: str = ""
    s2_api_key: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""  # empty → send.py falls back to smtp_username

    @classmethod
    def from_env(cls, *, s2_key_override: str = "",
                 env: Mapping | None = None) -> "PlatformCredentials":
        """Read credentials from the environment. s2_key_override preserves
        the historical quirk that a non-empty config.SEMANTIC_SCHOLAR_API_KEY
        beats the environment variable (search.py pre-refactor); pass it only
        when assembling from config.py."""
        if env is None:
            env = os.environ
        return cls(
            anthropic_api_key=env.get("ANTHROPIC_API_KEY", ""),
            openai_api_key=env.get("OPENAI_API_KEY", ""),
            ncbi_api_key=env.get("NCBI_API_KEY", ""),
            s2_api_key=s2_key_override or env.get("SEMANTIC_SCHOLAR_API_KEY", ""),
            smtp_host=env.get("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(env.get("SMTP_PORT", "587")),
            smtp_username=env.get("SMTP_USERNAME", ""),
            smtp_password=env.get("SMTP_PASSWORD", ""),
            email_from=env.get("EMAIL_FROM", ""),
        )


@dataclass
class RunResult:
    """What one pipeline run produced. status is one of:
    "sent" | "dry_run" | "search_only" | "no_papers" | "no_passed"."""

    status: str
    run_date: str = ""
    total_searched: int = 0
    passed_count: int = 0
    top_papers: list = field(default_factory=list)
    all_scored: list = field(default_factory=list)
    profile_text: str = ""
    digest_text: str = ""
    digest_html: str = ""
    full_list_html: str = ""
    record_path: str = ""   # "" when no run record was written
    preview_path: str = ""  # "" unless dry_run wrote the preview file
