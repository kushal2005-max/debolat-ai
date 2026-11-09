r"""
Debolat AI - Connect AI helper (called by Electron).

Usage:  python connect_ai.py '<json payload>'

Actions (payload {"action": ...}):
  registry         -> {"providers": [...]}   the list that builds the Connect AI panel
  test             -> {"ok": true} or {"ok": false, "error": ..., "kind": ...}
                      payload: {"action":"test","provider":"openai","model":"..."}
                      The API key is read from the DEBOLAT_AI_KEY environment
                      variable (never from argv, which other programs can see).
  ollama_models    -> {"ok": true, "models": [...]} or {"ok": false, ...}

Prints one JSON object to stdout. Diagnostics go to stderr.
"""

import os
import sys
import json

from providers import PROVIDERS, ProviderError, call_provider, get_provider, list_ollama_models


def action_test(payload):
    provider_id = payload.get("provider")
    provider = get_provider(provider_id)
    if provider is None:
        return {"ok": False, "kind": "other", "error": f"Unknown AI provider: {provider_id}"}

    key = os.environ.get("DEBOLAT_AI_KEY", "")
    model = (payload.get("model") or "").strip()

    try:
        extra = {}
        if provider_id == "ollama":
            models = list_ollama_models()
            if not models:
                return {"ok": False, "kind": "other",
                        "error": "Ollama is running but has no models yet. Open a terminal and run: ollama pull llama3.2"}
            extra["models"] = models
            if not model or model not in models:
                model = models[0]
        reply = call_provider(provider_id, key, model, "Reply with the single word OK.")
        if not reply.strip():
            return {"ok": False, "kind": "other", "error": "The AI connected but sent back an empty reply."}
        return {"ok": True, "model": model or provider["default_model"], **extra}
    except ProviderError as e:
        return {"ok": False, "kind": e.kind, "error": e.message}


def main():
    try:
        payload = json.loads(sys.argv[1])
    except (IndexError, json.JSONDecodeError):
        print(json.dumps({"ok": False, "error": "Invalid payload"}))
        sys.exit(1)

    action = payload.get("action")
    if action == "registry":
        print(json.dumps({"providers": PROVIDERS}))
    elif action == "test":
        print(json.dumps(action_test(payload)))
    elif action == "ollama_models":
        try:
            print(json.dumps({"ok": True, "models": list_ollama_models()}))
        except ProviderError as e:
            print(json.dumps({"ok": False, "kind": e.kind, "error": e.message}))
    else:
        print(json.dumps({"ok": False, "error": f"Unknown action: {action}"}))


if __name__ == "__main__":
    main()
