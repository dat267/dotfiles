#!/usr/bin/env python3
"""Generate charm-hyper model catalog into dot_pi/agent/extensions/charm-hyper/models.json.

Fetches the live /v1/models catalog from hyper.charm.land and produces the
static JSON format matching pi's built-in provider catalog pattern (used by
opencode-go, etc.). Run this to refresh the catalog, then commit the result.

Usage:
    cd ~/.local/share/chezmoi
    python3 dot_local/scripts/py/executable_generate-charm-models.py
"""

import json
import os
import sys
import urllib.request

MODELS_URL = "https://hyper.charm.land/v1/models"
BASE_URL = "https://hyper.charm.land/v1"
API = "openai-completions"
PROVIDER_ID = "charm-hyper"

OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "dot_pi", "agent", "extensions", "charm-hyper", "models.json",
)

PI_TO_PROVIDER = {
    "off": "none", "minimal": "minimal", "low": "low",
    "medium": "medium", "high": "high", "xhigh": "xhigh", "max": "max",
}


def fetch_models():
    with urllib.request.urlopen(MODELS_URL, timeout=15) as resp:
        return json.load(resp)["data"]


def to_model(m):
    reasoning = (m.get("reasoning") or {}).get("effort_levels") or []
    vision = bool((m.get("capabilities") or {}).get("vision"))
    pricing = m.get("pricing") or {}
    model = {
        "id": m["id"], "name": m.get("display_name", m["id"]),
        "api": API, "provider": PROVIDER_ID,
        "baseUrl": BASE_URL,
        "reasoning": bool(reasoning),
        "input": ["text", "image"] if vision else ["text"],
        "cost": {
            "input": pricing.get("input", 0),
            "output": pricing.get("output", 0),
            "cacheRead": pricing.get("cache_hit", 0),
            "cacheWrite": pricing.get("cache_create", 0),
        },
        "contextWindow": m.get("context_window", 128000),
        "maxTokens": m.get("max_output_tokens", 16384),
    }
    if reasoning:
        present = {e["value"] for e in reasoning}
        model["thinkingLevelMap"] = {
            k: (v if v in present else None) for k, v in PI_TO_PROVIDER.items()
        }
    return model


def main():
    data = fetch_models()
    models = {m["id"]: to_model(m) for m in data}
    catalog = {API: models}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(catalog, fh, indent=2)
        fh.write("\n")

    print(f"Generated {len(models)} charm-hyper models -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()