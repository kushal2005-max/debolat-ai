"""
Debolat AI - AI provider registry + one function to call any of them.

To add another AI later: add one entry to PROVIDERS and, if it isn't
OpenAI-compatible, one _call_* function. Nothing else in the app changes -
the Connect AI panel is built from this list.

Every provider function takes (api_key, model, prompt) and returns the raw
text the model answered with, or raises ProviderError(kind, message):
    kind = "auth"   -> key rejected / missing
           "quota"  -> rate limit or quota used up
           "busy"   -> temporary server problem, worth retrying
           "offline"-> local AI (Ollama) is not running
           "other"  -> anything else
"""

import json

import requests

TIMEOUT_SECONDS = 90


class ProviderError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind
        self.message = message


# NOTE: default_model values can be changed by the user in the panel. If a
# provider retires a model name, the "Test connection" step shows the error
# and the user just types a current one - no code change needed.
PROVIDERS = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "needs_key": True,
        "key_url": "https://aistudio.google.com/apikey",
        "key_button": "Get Gemini API key",
        "default_model": "gemini-3.6-flash",
        "location": "cloud",
        "note": "Has a free tier. Good default.",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "needs_key": True,
        "key_url": "https://platform.openai.com/api-keys",
        "key_button": "Get OpenAI API key",
        "default_model": "gpt-5-mini",
        "location": "cloud",
        "note": "Paid: needs billing set up on the OpenAI platform.",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "needs_key": True,
        "key_url": "https://console.anthropic.com/settings/keys",
        "key_button": "Get Claude API key",
        "default_model": "claude-haiku-5-5",
        "location": "cloud",
        "note": "Paid: needs credits on the Anthropic Console.",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "needs_key": True,
        "key_url": "https://openrouter.ai/settings/keys",
        "key_button": "Get OpenRouter API key",
        "default_model": "openai/gpt-5-mini",
        "location": "cloud",
        "note": "One key, many models (some free).",
    },
    {
        "id": "ollama",
        "name": "Ollama (on this PC)",
        "needs_key": False,
        "key_url": "https://ollama.com/download",
        "key_button": "Get Ollama",
        "default_model": "",
        "location": "local",
        "note": "Free and private: nothing leaves your computer.",
    },
]


def get_provider(provider_id):
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    return None


# ---------------------------------------------------------------- helpers

def _http_error(resp):
    """Turns a non-200 requests response into a ProviderError."""
    try:
        body = resp.json()
        detail = (body.get("error") or {})
        detail = detail.get("message") if isinstance(detail, dict) else str(detail)
    except Exception:
        detail = None
    detail = (detail or resp.text or "").strip()[:300]
    code = resp.status_code
    if code in (401, 403):
        return ProviderError("auth", f"The key was rejected ({code}). {detail}")
    if code == 429:
        return ProviderError("quota", f"Rate limit or quota reached. {detail}")
    if code >= 500:
        return ProviderError("busy", f"The AI service is busy ({code}). {detail}")
    return ProviderError("other", f"Request failed ({code}). {detail}")


def _post(url, headers, payload):
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.ConnectionError:
        raise ProviderError("offline", f"Could not reach {url.split('/')[2]}. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise ProviderError("busy", "The AI took too long to answer.")
    if resp.status_code != 200:
        raise _http_error(resp)
    return resp.json()


# -------------------------------------------------------------- providers

def _call_gemini(api_key, model, prompt):
    # The SDK is used (not raw REST) because the newer AQ.-style keys only
    # work through it.
    from google import genai
    from google.genai import errors as genai_errors

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text or ""
    except genai_errors.ClientError as e:
        text = str(e)
        if "429" in text or "RESOURCE_EXHAUSTED" in text:
            raise ProviderError("quota", "Gemini quota reached for this key.")
        if any(c in text for c in ("API key not valid", "API_KEY_INVALID", "401", "403", "PERMISSION_DENIED")):
            raise ProviderError("auth", "Gemini rejected this key.")
        raise ProviderError("other", text[:300])
    except genai_errors.ServerError as e:
        raise ProviderError("busy", f"Gemini is busy: {str(e)[:200]}")
    except ProviderError:
        raise
    except Exception as e:
        # Network trouble (no internet, proxy, DNS, timeout) surfaces from the
        # SDK as assorted httpx/OS errors - report it plainly instead of crashing.
        name = type(e).__name__
        if any(t in name for t in ("Connect", "Timeout", "Proxy", "Network", "Read", "OSError")):
            raise ProviderError("offline", "Could not reach Google. Check your internet connection.")
        raise ProviderError("other", f"{name}: {str(e)[:200]}")


def _call_openai_compatible(url, api_key, model, prompt, extra_headers=None):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    headers.update(extra_headers or {})
    data = _post(url, headers, {"model": model, "messages": [{"role": "user", "content": prompt}]})
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise ProviderError("other", f"Unexpected response shape: {json.dumps(data)[:200]}")


def _call_openai(api_key, model, prompt):
    return _call_openai_compatible("https://api.openai.com/v1/chat/completions", api_key, model, prompt)


def _call_openrouter(api_key, model, prompt):
    return _call_openai_compatible(
        "https://openrouter.ai/api/v1/chat/completions", api_key, model, prompt,
        extra_headers={"X-Title": "Debolat AI"},
    )


def _call_anthropic(api_key, model, prompt):
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    data = _post("https://api.anthropic.com/v1/messages", headers,
                 {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]})
    try:
        return "".join(block.get("text", "") for block in data["content"])
    except (KeyError, TypeError):
        raise ProviderError("other", f"Unexpected response shape: {json.dumps(data)[:200]}")


OLLAMA_URL = "http://localhost:11434"


def list_ollama_models():
    """Models installed in a running Ollama, or raises ProviderError('offline')."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
    except requests.exceptions.RequestException:
        raise ProviderError("offline", "Ollama isn't running on this PC (or isn't installed).")
    if resp.status_code != 200:
        raise ProviderError("other", f"Ollama answered with status {resp.status_code}.")
    return [m["name"] for m in resp.json().get("models", [])]


def _call_ollama(api_key, model, prompt):
    if not model:
        models = list_ollama_models()
        if not models:
            raise ProviderError("other", "Ollama is running but has no models yet. Run: ollama pull llama3.2")
        model = models[0]
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "stream": False, "format": "json",
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=300,  # local models can be slow on the first call
        )
    except requests.exceptions.ConnectionError:
        raise ProviderError("offline", "Ollama isn't running on this PC.")
    except requests.exceptions.Timeout:
        raise ProviderError("busy", "The local model took too long to answer.")
    if resp.status_code != 200:
        raise _http_error(resp)
    return resp.json().get("message", {}).get("content", "")


_CALLERS = {
    "gemini": _call_gemini,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "openrouter": _call_openrouter,
    "ollama": _call_ollama,
}


def call_provider(provider_id, api_key, model, prompt):
    """Sends `prompt` to the provider and returns its raw text answer."""
    provider = get_provider(provider_id)
    caller = _CALLERS.get(provider_id)
    if provider is None or caller is None:
        raise ProviderError("other", f"Unknown AI provider: {provider_id}")
    if provider["needs_key"] and not api_key:
        raise ProviderError("auth", f"No API key set for {provider['name']}.")
    return caller(api_key, model or provider["default_model"], prompt)
