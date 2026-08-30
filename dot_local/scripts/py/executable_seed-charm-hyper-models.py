#!/usr/bin/env python3
"""Seed the charm-hyper model catalog into pi's ~/.pi/agent/models-store.json.

pi restores model catalogs from models-store.json offline at startup, so a
provider whose catalog is present there is available immediately with no
network fetch (identical to how pi's built-in providers behave). This script
fetches charm-hyper's /v1/models catalog, maps it to pi's Model shape, and
writes it under the "charm-hyper" key, preserving any other providers already
stored.

Run manually:
    python3 seed-charm-hyper-models.py

Or re-run to refresh; the on-disk entry's checkedAt is updated each run.
"""

import json
import os
import sys
import time
import urllib.request

MODELS_URL = "https://hyper.charm.land/v1/models"
BASE_URL = "https://hyper.charm.land/v1"
PROVIDER_ID = "charm-hyper"
API = "openai-completions"

OUT_PATH = os.path.expanduser("~/.pi/agent/models-store.json")

# Map pi thinking levels to charm-hyper effort level values.
PI_TO_PROVIDER = {
    "off": "none",
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
}


def build_thinking_map(effort_levels):
    if not effort_levels:
        return None
    present = {e.get("value") for e in effort_levels}
    return {pi: (pv if pv in present else None) for pi, pv in PI_TO_PROVIDER.items()}


def fetch_models():
    with urllib.request.urlopen(MODELS_URL, timeout=15) as resp:
        payload = json.load(resp)
    return payload.get("data") or []


def to_model(m):
    reasoning = bool((m.get("reasoning") or {}).get("effort_levels"))
    vision = bool((m.get("capabilities") or {}).get("vision"))
    pricing = m.get("pricing") or {"input": 0, "output": 0, "cache_create": 0, "cache_hit": 0}
    return {
        "id": m["id"],
        "name": m.get("display_name", m["id"]),
        "api": API,
        "provider": PROVIDER_ID,
        "baseUrl": BASE_URL,
        "reasoning": reasoning,
        "input": ["text", "image"] if vision else ["text"],
        "cost": {
            "input": pricing.get("input", 0),
            "output": pricing.get("output", 0),
            "cacheRead": pricing.get("cache_hit", 0),
            "cacheWrite": pricing.get("cache_create", 0),
        },
        "contextWindow": m.get("context_window", 0),
        "maxTokens": m.get("max_output_tokens", 0),
        "thinkingLevelMap": build_thinking_map((m.get("reasoning") or {}).get("effort_levels")),
    }


def main():
    try:
        data = fetch_models()
    except Exception as err:
        print(f"error: could not fetch {MODELS_URL}: {err}", file=sys.stderr)
        sys.exit(1)

    if not data:
        print("error: no models returned", file=sys.stderr)
        sys.exit(1)

    models = [to_model(m) for m in data]

    store = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH) as fh:
                store = json.load(fh)
        except (json.JSONDecodeError, OSError):
            store = {}

    store[PROVIDER_ID] = {
        "models": models,
        "checkedAt": int(time.time() * 1000),
        "lastModified": int(time.time() * 1000),
        "etag": None,
    }

    with open(OUT_PATH, "w") as fh:
        json.dump(store, fh, indent=2)

    print(f"seeded {len(models)} charm-hyper models into {OUT_PATH}")


if __name__ == "__main__":
    main()