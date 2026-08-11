# llm.py — provider-agnostic LLM wrapper
# To switch providers: change LLM_PROVIDER and LLM_MODEL in config.py only.

import os
from dotenv import load_dotenv
import config

load_dotenv(os.path.expanduser("~/.env"))


def call_llm(prompt: str, system: str = "") -> str:
    """
    Send a prompt to the configured LLM provider and return the response text.
    All scoring and summarization in the agent goes through this function.
    """
    provider = config.LLM_PROVIDER.lower()

    if provider == "anthropic":
        return _call_anthropic(prompt, system)
    elif provider == "openai":
        return _call_openai(prompt, system)
    elif provider == "ollama":
        return _call_ollama(prompt, system)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}' in config.py. "
            "Choose: 'anthropic', 'openai', or 'ollama'."
        )


def _call_anthropic(prompt: str, system: str) -> str:
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        timeout=45.0,  # 45-second hard timeout per call
    )
    kwargs = {
        "model": config.LLM_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    return msg.content[0].text


def _call_openai(prompt: str, system: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        max_tokens=1024,
    )
    return resp.choices[0].message.content


def _call_ollama(prompt: str, system: str) -> str:
    # Requires Ollama running locally: https://ollama.com
    # Pull a model first: ollama pull llama3
    import requests
    payload = {
        "model": config.LLM_MODEL,
        "prompt": f"{system}\n\n{prompt}" if system else prompt,
        "stream": False,
    }
    resp = requests.post("http://localhost:11434/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json()["response"]
