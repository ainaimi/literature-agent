# Tests for models.py — the settings/credentials data contracts.
#
# The from_config_module tests run against the LIVE config.py on purpose:
# they are the guarantee that the refactored pipeline sees exactly the values
# the single-user tool has always read.

import pytest

import config
import models
from models import (CONFIG_FIELD_MAP, CONFIG_NAMES_NOT_MAPPED, DEFAULT_PERSONA,
                    PlatformCredentials, UserSettings)


# ─── UserSettings: dict round-trip and from_dict ─────────────────────────────

def test_to_dict_from_dict_round_trip():
    s = UserSettings.from_config_module(config, env={"EMAIL_TO": "a@b.edu"})
    assert UserSettings.from_dict(s.to_dict()) == s


def test_from_dict_rejects_unknown_keys():
    with pytest.raises(ValueError, match="lookback_dayz"):
        UserSettings.from_dict({"lookback_dayz": 14})


def test_from_dict_derives_tenant_paths_from_data_dir():
    s = UserSettings.from_dict({"data_dir": "tenants/bob"})
    assert s.interests_dir == "tenants/bob/interests"
    assert s.profile_cache_file == "tenants/bob/_profile_cache.json"


def test_from_dict_explicit_paths_beat_derivation():
    s = UserSettings.from_dict({"data_dir": "tenants/bob",
                                "interests_dir": "/elsewhere/papers"})
    assert s.interests_dir == "/elsewhere/papers"
    assert s.profile_cache_file == "tenants/bob/_profile_cache.json"


def test_from_dict_default_data_dir_keeps_legacy_paths():
    s = UserSettings.from_dict({})
    assert s.interests_dir == "./interests"
    assert s.profile_cache_file == "./_profile_cache.json"


# ─── UserSettings: config.py equivalence ─────────────────────────────────────

def test_from_config_module_matches_live_config():
    s = UserSettings.from_config_module(config, env={"EMAIL_TO": "a@b.edu"})
    assert s.llm_provider == config.LLM_PROVIDER
    assert s.llm_model == config.LLM_MODEL
    assert s.databases == config.DATABASES
    assert s.cluster_databases == config.CLUSTER_DATABASES
    assert s.arxiv_categories == config.ARXIV_CATEGORIES
    assert s.search_clusters == config.SEARCH_CLUSTERS
    assert s.followed_authors == config.FOLLOWED_AUTHORS
    assert s.exclude_keywords == config.EXCLUDE_KEYWORDS
    assert s.require_keywords == config.REQUIRE_KEYWORDS
    assert s.lookback_days == config.LOOKBACK_DAYS
    assert s.fetch_limit_per_query == config.FETCH_LIMIT_PER_QUERY
    assert s.relevance_threshold == config.RELEVANCE_THRESHOLD
    assert s.top_n_papers == config.TOP_N_PAPERS
    assert s.skip_seen_papers == config.SKIP_SEEN_PAPERS
    assert s.seen_retention_days == config.SEEN_RETENTION_DAYS
    assert s.interests_dir == config.INTERESTS_DIR
    assert s.profile_cache_file == config.PROFILE_CACHE_FILE
    assert s.profile_max_age_days == config.PROFILE_MAX_AGE_DAYS
    assert s.email_subject == config.EMAIL_SUBJECT
    assert s.email_to == "a@b.edu"
    assert s.data_dir == "."


def test_from_config_module_defaults_persona_and_example_name():
    # config.py has no PERSONA/EXAMPLE_NAME today — the historical values
    # must apply so scoring prompts stay byte-identical.
    s = UserSettings.from_config_module(config, env={})
    assert s.persona == DEFAULT_PERSONA
    assert s.example_name == "Naimi"


def test_from_config_module_does_not_alias_config_mutables():
    s = UserSettings.from_config_module(config, env={})
    assert s.search_clusters is not config.SEARCH_CLUSTERS
    first_cluster = next(iter(s.search_clusters))
    assert s.search_clusters[first_cluster] is not config.SEARCH_CLUSTERS[first_cluster]


def test_from_config_module_tolerates_missing_optional_sections():
    # search.py historically used getattr defaults for these — a config.py
    # with sections deleted must yield defaults, not AttributeError.
    class MinimalConfig:
        pass

    s = UserSettings.from_config_module(MinimalConfig, env={})
    assert s.cluster_databases == {}
    assert s.arxiv_categories == []
    assert s.exclude_keywords == []
    assert s.require_keywords == []
    assert s.lookback_days == 7


def test_config_parity_every_config_name_is_consumed():
    # A new UPPERCASE knob added to config.py must be wired into
    # CONFIG_FIELD_MAP (or deliberately excluded) — never silently ignored.
    config_names = {n for n in vars(config) if n.isupper()}
    unaccounted = config_names - set(CONFIG_FIELD_MAP) - CONFIG_NAMES_NOT_MAPPED
    assert not unaccounted, (
        f"config.py names not consumed by UserSettings.from_config_module: "
        f"{sorted(unaccounted)}")


# ─── UserSettings: derived paths ─────────────────────────────────────────────

def test_default_data_dir_yields_legacy_artifact_paths():
    # The GitHub Actions artifact globs (_runs/*.json, _last_run.json) and the
    # printed progress lines depend on these literal strings.
    s = UserSettings()
    assert s.last_run_path == "_last_run.json"
    assert s.runs_dir == "_runs"
    assert s.preview_path == "_full-scored-list-preview.html"
    assert s.seen_path == "_seen.json"


def test_tenant_data_dir_scopes_artifact_paths():
    s = UserSettings(data_dir="tenants/bob")
    assert s.last_run_path == "tenants/bob/_last_run.json"
    assert s.runs_dir == "tenants/bob/_runs"
    assert s.preview_path == "tenants/bob/_full-scored-list-preview.html"
    assert s.seen_path == "tenants/bob/_seen.json"


# ─── PlatformCredentials ─────────────────────────────────────────────────────

def test_from_env_reads_all_names():
    env = {
        "ANTHROPIC_API_KEY": "ak", "OPENAI_API_KEY": "ok",
        "NCBI_API_KEY": "nk", "SEMANTIC_SCHOLAR_API_KEY": "sk",
        "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "2525",
        "SMTP_USERNAME": "u@example.com", "SMTP_PASSWORD": "pw",
        "EMAIL_FROM": "from@example.com",
    }
    c = PlatformCredentials.from_env(env=env)
    assert c.anthropic_api_key == "ak"
    assert c.openai_api_key == "ok"
    assert c.ncbi_api_key == "nk"
    assert c.s2_api_key == "sk"
    assert c.smtp_host == "smtp.example.com"
    assert c.smtp_port == 2525
    assert c.smtp_username == "u@example.com"
    assert c.smtp_password == "pw"
    assert c.email_from == "from@example.com"


def test_from_env_defaults():
    c = PlatformCredentials.from_env(env={})
    assert c.smtp_host == "smtp.gmail.com"
    assert c.smtp_port == 587
    assert c.anthropic_api_key == ""
    assert c.email_from == ""


def test_s2_key_config_override_beats_env():
    # Historical precedence (search.py pre-refactor): non-empty config value
    # wins; empty config value falls through to the environment.
    env = {"SEMANTIC_SCHOLAR_API_KEY": "envkey"}
    assert PlatformCredentials.from_env(s2_key_override="cfgkey", env=env).s2_api_key == "cfgkey"
    assert PlatformCredentials.from_env(s2_key_override="", env=env).s2_api_key == "envkey"
    assert PlatformCredentials.from_env(env={}).s2_api_key == ""
