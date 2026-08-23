# llm.py — provider-agnostic LLM wrapper


def call(prompt: str, system: str = "", *, provider: str, model: str,
         anthropic_api_key: str = "", openai_api_key: str = "",
         timeout: float = 45.0) -> str:
    """
    Send a prompt to the given LLM provider and return the response text.
    All scoring and summarization in the agent goes through this function.
    """
    provider = provider.lower()

    if provider == "anthropic":
        if not anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — required when "
                               "LLM_PROVIDER is 'anthropic'.")
        return _call_anthropic(prompt, system, model=model,
                               api_key=anthropic_api_key, timeout=timeout)
    elif provider == "openai":
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set — required when "
                               "LLM_PROVIDER is 'openai'.")
        return _call_openai(prompt, system, model=model,
                            api_key=openai_api_key, timeout=timeout)
    elif provider == "ollama":
        return _call_ollama(prompt, system, model=model, timeout=timeout)
    else:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            "Choose: 'anthropic', 'openai', or 'ollama'."
        )


def make_llm_call(settings, credentials):
    """Bind a UserSettings + PlatformCredentials pair into the simple
    llm_call(prompt, system="") callable the pipeline modules take."""
    def llm_call(prompt: str, system: str = "") -> str:
        return call(prompt, system,
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                    anthropic_api_key=credentials.anthropic_api_key,
                    openai_api_key=credentials.openai_api_key)
    return llm_call


def _call_anthropic(prompt: str, system: str, *, model: str, api_key: str,
                    timeout: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    kwargs = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    return msg.content[0].text


def _call_openai(prompt: str, system: str, *, model: str, api_key: str,
                 timeout: float) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, timeout=timeout)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=1024,
    )
    return resp.choices[0].message.content


def _call_ollama(prompt: str, system: str, *, model: str, timeout: float) -> str:
    # Requires Ollama running locally: https://ollama.com
    # Pull a model first: ollama pull llama3
    import requests
    payload = {
        "model": model,
        "prompt": f"{system}\n\n{prompt}" if system else prompt,
        "stream": False,
    }
    resp = requests.post("http://localhost:11434/api/generate", json=payload,
                         timeout=timeout)
    resp.raise_for_status()
    return resp.json()["response"]


# ─── TEMPORARY back-compat shim ──────────────────────────────────────────────
# Old zero-config entry point, still used by profiles.py and score.py until
# their migrations land. Deleted once no callers remain.

def call_llm(prompt: str, system: str = "") -> str:
    import os

    import config
    return call(prompt, system,
                provider=config.LLM_PROVIDER,
                model=config.LLM_MODEL,
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""))
