#!/usr/bin/env python3
"""hyper-catalog — regenerate hyper/catalog.ts from the live /v1/models API.

hyper publishes authoritative pricing, context windows, output caps, effort
levels, and vision flags at GET https://hyper.charm.land/v1/models. The
provider extension's catalog is hand-curated (model selection and display
names stay human decisions — the API's names are cosmetic and ours read
better), but every data field the API publishes is derived: this tool
rewrites the CATALOG array in catalog.ts to match the API exactly, leaving
the rest of the file (interface, compat constants, toModel, buildModels)
untouched. Review happens as a git diff.

Effort vocabulary: the API also offers "none" and "minimal", which the
compact catalog cannot express — they are dropped (pi's "off"/"minimal"
thinking levels stay unmapped).

Auth: --api-key flag > $HYPER_API_KEY > ~/.pi/agent/auth.json (provider id
"hyper"), same precedence as the extension.

Run from the repo root (or pass --file):
    hyper-catalog --check    # report drift, change nothing, exit 1 on drift
    hyper-catalog            # rewrite the CATALOG array in place
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API_URL = "https://hyper.charm.land/v1/models"
DEFAULT_FILE = Path("dot_pi/agent/exact_extensions/exact_providers/hyper/catalog.ts")
AUTH_PATH = Path("~/.pi/agent/auth.json").expanduser()
TIMEOUT = 30

# Provider effort values the compact catalog can express, in canonical order.
EFFORTS = ("low", "medium", "high", "xhigh", "max")

# One compact entry block as the generator emits (and parses) it.
ENTRY_RE = re.compile(
    r"\t\{\n"
    r'\t\tid:\s*"([^"]+)",\s*name:\s*"([^"]+)",\s*reasoning:\s*(true|false)'
    r"(?:,\s*vision:\s*(true|false))?\s*,\n"
    r"\t\tefforts:\s*\[([^\]]*)\],\n"
    r"\t\tcost:\s*\{\s*input:\s*([\d.]+),\s*output:\s*([\d.]+),"
    r"\s*cacheRead:\s*([\d.]+),\s*cacheWrite:\s*([\d.]+)\s*\},\n"
    r"\t\tcontextWindow:\s*([\d_]+),\s*maxTokens:\s*([\d_]+),\n"
    r"\t\},\n?"
)
CATALOG_RE = re.compile(r"(const CATALOG: CompactEntry\[\] = \[\n)(.*?)(\n\];)", re.S)


def ts_number(value, underscores=False):
    """Catalog-style literal: 0.031575 stays float, 2.0 prints as 2, limits
    get underscore separators (1_048_576)."""
    if underscores:
        return f"{int(value):,}".replace(",", "_")
    number = float(value)
    return str(int(number)) if number.is_integer() else repr(number)


def emit_entry(entry):
    """One compact entry block, in the catalog's own style."""
    head = f'\t\tid: "{entry["id"]}", name: "{entry["name"]}", reasoning: {str(entry["reasoning"]).lower()}'
    if entry["vision"]:
        head += ", vision: true"
    efforts = ", ".join(f'"{e}"' for e in entry["efforts"])
    cost = ", ".join(
        f"{field}: {ts_number(entry['cost'][field])}"
        for field in ("input", "output", "cacheRead", "cacheWrite")
    )
    return (
        "\t{\n"
        f"{head},\n"
        f"\t\tefforts: [{efforts}],\n"
        f"\t\tcost: {{ {cost} }},\n"
        f"\t\tcontextWindow: {ts_number(entry['contextWindow'], underscores=True)},"
        f" maxTokens: {ts_number(entry['maxTokens'], underscores=True)},\n"
        "\t},\n"
    )


def parse_entries(source):
    """Parse the compact entries out of a catalog.ts source, in file order."""
    match = CATALOG_RE.search(source)
    if not match:
        raise ValueError("no `const CATALOG: CompactEntry[] = [...]` array found")
    entries = []
    for m in ENTRY_RE.finditer(match.group(2)):
        entries.append({
            "id": m.group(1),
            "name": m.group(2),
            "reasoning": m.group(3) == "true",
            "vision": m.group(4) == "true",
            "efforts": [e.strip(' "') for e in m.group(5).split(",") if e.strip()],
            "cost": {
                "input": float(m.group(6)),
                "output": float(m.group(7)),
                "cacheRead": float(m.group(8)),
                "cacheWrite": float(m.group(9)),
            },
            "contextWindow": int(m.group(10).replace("_", "")),
            "maxTokens": int(m.group(11).replace("_", "")),
        })
    if not entries:
        raise ValueError("no compact entries parsed from the CATALOG array")
    return entries


def diff_catalog(source, models):
    """Field-level drift between a catalog.ts source and the API models.

    Returns {changes: [{id, field, old, new}], missing: [...], api_only: [...]}
    — the report a --check run prints and the write run summarizes."""
    entries = parse_entries(source)
    changes = []
    for old in entries:
        model = models.get(old["id"])
        if model is None:
            continue
        new = entry_from_api(model)
        for field in ("reasoning", "vision", "efforts", "contextWindow", "maxTokens"):
            if old[field] != new[field]:
                changes.append({"id": old["id"], "field": field, "old": old[field], "new": new[field]})
        for field in ("input", "output", "cacheRead", "cacheWrite"):
            if old["cost"][field] != new["cost"][field]:
                changes.append({
                    "id": old["id"], "field": f"cost.{field}",
                    "old": old["cost"][field], "new": new["cost"][field],
                })
    known = {e["id"] for e in entries}
    return {
        "changes": changes,
        "missing": [e["id"] for e in entries if e["id"] not in models],
        "api_only": sorted(mid for mid in models if mid not in known),
    }


def regenerate(source, models):
    """Rewrite the CATALOG array in catalog.ts source to match the API.

    Curated order and model selection are preserved: every parsed entry is
    re-emitted from the API when its id is known, or kept verbatim when it is
    not. Everything outside the array is untouched, and anything inside the
    array the parser does not recognize aborts rather than being dropped."""
    match = CATALOG_RE.search(source)
    if not match:
        raise ValueError("no `const CATALOG: CompactEntry[] = [...]` array found")
    body = match.group(2)
    blocks = []
    pos = 0
    for entry_match in ENTRY_RE.finditer(body):
        gap = body[pos : entry_match.start()]
        if gap.strip():
            raise ValueError(f"unrecognized content in CATALOG array: {gap[:60]!r}")
        mid = entry_match.group(1)
        if mid in models:
            entry = entry_from_api(models[mid])
            # Display names stay curated: the API's are cosmetic and ours read
            # better in pi's model picker. Data fields follow the API.
            entry["name"] = entry_match.group(2)
            blocks.append(emit_entry(entry).rstrip("\n"))
        else:
            blocks.append(entry_match.group(0).rstrip("\n"))
        pos = entry_match.end()
    tail = body[pos:]
    if tail.strip():
        raise ValueError(f"unrecognized content in CATALOG array: {tail[:60]!r}")
    if not blocks:
        raise ValueError("no compact entries parsed from the CATALOG array")
    return source[: match.start(2)] + "\n".join(blocks) + tail + source[match.end(2) :]


def parse_api_models(data):
    """Extract id -> normalized model record from a /v1/models response."""
    models = {}
    for raw in data.get("data", []):
        mid = raw.get("id")
        if not isinstance(mid, str) or not mid:
            continue
        pricing = raw.get("pricing") or {}
        efforts = [
            level.get("value")
            for level in (raw.get("reasoning") or {}).get("effort_levels") or []
            if isinstance(level, dict)
        ]
        models[mid] = {
            "id": mid,
            "name": raw.get("display_name") or mid,
            "contextWindow": raw.get("context_window"),
            "maxTokens": raw.get("max_output_tokens"),
            "vision": bool((raw.get("capabilities") or {}).get("vision")),
            "efforts": [e for e in efforts if e in EFFORTS],
            "cost": {
                "input": pricing.get("input"),
                "output": pricing.get("output"),
                "cacheRead": pricing.get("cache_hit"),
                "cacheWrite": pricing.get("cache_create"),
            },
        }
    return models


def entry_from_api(model):
    """Map a normalized API model record to a compact catalog entry."""
    return {
        "id": model["id"],
        "name": model["name"],
        "reasoning": bool(model["efforts"]),
        "vision": model["vision"],
        "efforts": model["efforts"],
        "cost": model["cost"],
        "contextWindow": model["contextWindow"],
        "maxTokens": model["maxTokens"],
    }


def eprint(*args):
    print(*args, file=sys.stderr)


def resolve_api_key(flag_value, env_value=None, auth_path=AUTH_PATH):
    """--api-key > $HYPER_API_KEY > ~/.pi/agent/auth.json (hyper.key)."""
    if flag_value:
        return flag_value
    if env_value is None:
        env_value = os.environ.get("HYPER_API_KEY")
    if env_value:
        return env_value
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        key = (auth.get("hyper") or {}).get("key")
        if key:
            return key
    except (OSError, ValueError):
        pass
    return None


def fetch_models(api_key, opener=None):
    """GET /v1/models with auth; the parsed model map, or None on failure."""
    open_url = opener or urllib.request.urlopen
    req = urllib.request.Request(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with open_url(req, timeout=TIMEOUT) as response:
            return parse_api_models(json.loads(response.read().decode("utf-8")))
    except Exception as error:  # transport or parse — both fatal for a sync
        eprint(f"fetching {API_URL} failed: {error}")
        return None


def format_report(report):
    """Human-readable drift report, one line per change."""
    lines = []
    for change in report["changes"]:
        lines.append(f"  {change['id']}: {change['field']} {change['old']!r} -> {change['new']!r}")
    for mid in report["missing"]:
        lines.append(f"  {mid}: not in the API, kept verbatim")
    if report["api_only"]:
        lines.append("  API models not in the catalog (curation is manual): " + ", ".join(report["api_only"]))
    return lines


def main(argv=None, opener=None):
    parser = argparse.ArgumentParser(
        description="Regenerate hyper/catalog.ts from the live /v1/models API",
    )
    parser.add_argument("--check", action="store_true",
                        help="report drift, write nothing, exit 1 on drift")
    parser.add_argument("--file", default=str(DEFAULT_FILE),
                        help=f"catalog.ts to sync (default: {DEFAULT_FILE} from cwd)")
    parser.add_argument("--api-key", default=None,
                        help="hyper API key (default: $HYPER_API_KEY or auth.json)")
    args = parser.parse_args(argv)

    target = Path(args.file)
    try:
        source = target.read_text(encoding="utf-8")
    except OSError as error:
        eprint(f"cannot read {target}: {error}")
        return 1

    api_key = resolve_api_key(args.api_key)
    if not api_key:
        eprint(f"no API key: pass --api-key, set $HYPER_API_KEY, or write hyper.key to {AUTH_PATH}")
        return 1

    models = fetch_models(api_key, opener=opener)
    if models is None:
        return 1

    try:
        report = diff_catalog(source, models)
    except ValueError as error:
        eprint(f"{target}: {error}")
        return 1

    lines = format_report(report)
    if not report["changes"]:
        eprint(f"{target}: in sync with the API" + (f" ({len(lines)} notes)" if lines else ""))
        for line in lines:
            eprint(line)
        return 0

    if args.check:
        eprint(f"{target}: {len(report['changes'])} drifted fields (--check, nothing written):")
        for line in lines:
            eprint(line)
        return 1

    try:
        target.write_text(regenerate(source, models), encoding="utf-8")
    except (OSError, ValueError) as error:
        eprint(f"{target}: {error}")
        return 1
    eprint(f"{target}: {len(report['changes'])} fields updated:")
    for line in lines:
        eprint(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
