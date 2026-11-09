"""
Debolat AI - AI Engine
Sends item data to whichever AI the user connected and returns a structured,
honesty-first explanation.

WHICH AI IS USED
  1. The AI the user connected in the app's "Connect AI" panel. Electron passes
     it to this process through environment variables (never on the command
     line): DEBOLAT_AI_PROVIDER, DEBOLAT_AI_KEY, DEBOLAT_AI_MODEL.
  2. If nothing is connected, the old developer fallback: Gemini keys from
     GEMINI_API_KEY, GEMINI_API_KEY_2, ... in .env (tries the next key when
     one runs out of quota). This is a dev convenience, not how real users
     should run the app.

Every provider goes through the same prompt and the same strict output check,
so the never-guess rule holds no matter which AI answers: a reply that is not
valid JSON in our format is reported as unusable instead of being shown.

Results are cached per run by cache_key so the same item is never asked twice.
"""

import os
import json
import time
import sys

from providers import call_provider, ProviderError

# --- Developer fallback keys (only used when no AI is connected in the app) ---
def _load_api_keys():
    keys = []
    first = os.environ.get("GEMINI_API_KEY")
    if first:
        keys.append(first)
    n = 2
    while True:
        next_key = os.environ.get(f"GEMINI_API_KEY_{n}")
        if not next_key:
            break
        keys.append(next_key)
        n += 1
    return keys


API_KEYS = _load_api_keys()
FALLBACK_MODEL = "gemini-3.6-flash"

PROMPT_TEMPLATE = """You are helping a user understand why an item on their \
Windows PC is taking up resources, so they can decide what to do about it.

You are only given objective, verifiable system data below - no information \
about how often the user actually uses this item. Do not assume usage \
patterns you were not given.

ITEM DATA:
{item_context}

INSTRUCTIONS:
- Explain in plain, non-technical English what this item most likely is \
and why it might be taking up the amount of space/RAM shown.
- Give a recommendation: KEEP, INVESTIGATE, or LIKELY_SAFE_TO_REMOVE.
- Classify the item_type as either "NAMED_APPLICATION" (a recognizable, \
named piece of software the user installed or runs on purpose - games, \
browsers, tools, launchers, chat apps, etc., even if this specific item is \
just one of that app's supporting folders/processes) or "GENERIC_JUNK" \
(temp files, caches, logs, crash dumps, or other data with no distinct \
identity of its own - the kind of thing no user would recognize as "an app"). \
When genuinely unsure which category fits, use "NAMED_APPLICATION" - it is \
safer to under-classify something as an app than to mistakenly wave through \
something a user would actually recognize and care about.
- CRITICAL: If you are not confident about what this item is or whether \
it's safe to touch, you MUST say so explicitly and use the recommendation \
"UNSURE - USER SHOULD DECIDE". Do not guess or make up a plausible-sounding \
explanation just to give an answer. Being wrong here can damage the \
user's system, so honesty about uncertainty matters more than sounding useful.

Respond ONLY with raw JSON in this exact format, no markdown fences:
{{
  "explanation": "plain English explanation",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "recommendation": "KEEP" | "INVESTIGATE" | "LIKELY_SAFE_TO_REMOVE" | "UNSURE - USER SHOULD DECIDE",
  "item_type": "NAMED_APPLICATION" | "GENERIC_JUNK",
  "reasoning": "why you gave this recommendation, including what evidence you're basing it on"
}}
"""


_result_cache = {}  # cache_key -> parsed AI result, for this run only

_VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
_VALID_RECOMMENDATION = {"KEEP", "INVESTIGATE", "LIKELY_SAFE_TO_REMOVE", "UNSURE - USER SHOULD DECIDE"}
_VALID_ITEM_TYPE = {"NAMED_APPLICATION", "GENERIC_JUNK"}


def _extract_json(raw_text):
    """Pulls a JSON object out of a model reply (handles code fences and
    chatty text around the JSON, which smaller models often add)."""
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    first, last = cleaned.find("{"), cleaned.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(cleaned[first:last + 1])
        except json.JSONDecodeError:
            pass
    return None


def _parse_and_validate(raw_text):
    """Returns a clean result dict, or an {"error": ...} dict. Never passes
    through a reply that doesn't match our schema - a wrong-shaped answer is
    worse than no answer for a tool that can delete things."""
    data = _extract_json(raw_text)
    if not isinstance(data, dict):
        return {"error": "The AI did not return a usable answer (not valid JSON).", "raw_response": raw_text[:500]}

    for field in ("explanation", "confidence", "recommendation", "item_type", "reasoning"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            return {"error": f"The AI's answer was missing '{field}'.", "raw_response": raw_text[:500]}

    data["confidence"] = data["confidence"].strip().upper()
    data["recommendation"] = data["recommendation"].strip().upper()
    data["item_type"] = data["item_type"].strip().upper()

    if data["confidence"] not in _VALID_CONFIDENCE:
        return {"error": "The AI gave an unrecognised confidence level.", "raw_response": raw_text[:500]}
    if data["recommendation"] not in _VALID_RECOMMENDATION:
        return {"error": "The AI gave an unrecognised recommendation.", "raw_response": raw_text[:500]}
    if data["item_type"] not in _VALID_ITEM_TYPE:
        return {"error": "The AI gave an unrecognised item type.", "raw_response": raw_text[:500]}
    return data


def _error_result(e):
    return {"error": e.message, "error_kind": e.kind}


def _ask_connected(prompt, provider, key, model, max_retries):
    """The user's own connected AI: one key, retry only when the service is busy."""
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            return _parse_and_validate(call_provider(provider, key, model, prompt))
        except ProviderError as e:
            last = e
            if e.kind != "busy" or attempt == max_retries:
                break
            wait = 2 * attempt
            print(f"  [AI busy, retrying in {wait}s (attempt {attempt}/{max_retries})...]", file=sys.stderr)
            time.sleep(wait)
    return _error_result(last)


def _ask_dev_fallback(prompt, max_retries):
    """Old behaviour: Gemini keys from .env, switching key when one hits quota."""
    last = None
    for key_index, key in enumerate(API_KEYS):
        for attempt in range(1, max_retries + 1):
            try:
                return _parse_and_validate(call_provider("gemini", key, FALLBACK_MODEL, prompt))
            except ProviderError as e:
                last = e
                if e.kind == "quota":
                    print(f"  [Key {key_index + 1} quota exhausted, trying next key if available...]", file=sys.stderr)
                    break
                if e.kind != "busy":
                    return _error_result(e)
                if attempt < max_retries:
                    time.sleep(2 * attempt)
    return {"error": "All available API keys exhausted or unavailable",
            "error_kind": last.kind if last else "other",
            "raw_response": last.message if last else ""}


def ask_ai(item_context, cache_key=None, max_retries=3):
    """
    Sends item_context to the connected AI and returns the validated result,
    or a dict with an "error" key. Never raises for AI/network problems.
    """
    provider = os.environ.get("DEBOLAT_AI_PROVIDER")
    key = os.environ.get("DEBOLAT_AI_KEY", "")
    model = os.environ.get("DEBOLAT_AI_MODEL", "")

    if not provider and not API_KEYS:
        return {"error": "No AI connected yet. Click \"Connect AI\" on the Home screen to set one up.",
                "error_kind": "not_connected"}

    if cache_key is not None and cache_key in _result_cache:
        print(f"  [Reusing cached result for '{cache_key}']", file=sys.stderr)
        return _result_cache[cache_key]

    prompt = PROMPT_TEMPLATE.format(item_context=item_context)

    try:
        if provider:
            result = _ask_connected(prompt, provider, key, model, max_retries)
        else:
            result = _ask_dev_fallback(prompt, max_retries)
    except Exception as e:  # last-resort net: the UI must always get JSON back
        result = {"error": f"Unexpected problem talking to the AI: {type(e).__name__}", "error_kind": "other"}

    if cache_key is not None and "error" not in result:
        _result_cache[cache_key] = result
    return result
