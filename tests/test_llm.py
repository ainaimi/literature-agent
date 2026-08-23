# Tests for llm.py — dispatch and key handling, providers monkeypatched.

import pytest

import llm
from models import PlatformCredentials, UserSettings


def test_call_raises_clear_error_on_missing_anthropic_key():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.call("hi", provider="anthropic", model="m")


def test_call_raises_clear_error_on_missing_openai_key():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm.call("hi", provider="openai", model="m")


def test_call_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        llm.call("hi", provider="gemini", model="m")


def test_make_llm_call_binds_settings_and_credentials(monkeypatch):
    seen = {}

    def fake_anthropic(prompt, system, *, model, api_key, timeout):
        seen.update(prompt=prompt, system=system, model=model,
                    api_key=api_key, timeout=timeout)
        return "response"

    monkeypatch.setattr(llm, "_call_anthropic", fake_anthropic)
    settings = UserSettings(llm_provider="anthropic", llm_model="test-model")
    creds = PlatformCredentials(anthropic_api_key="ak")
    llm_call = llm.make_llm_call(settings, creds)

    assert llm_call("the prompt", system="the system") == "response"
    assert seen == {"prompt": "the prompt", "system": "the system",
                    "model": "test-model", "api_key": "ak", "timeout": 45.0}
