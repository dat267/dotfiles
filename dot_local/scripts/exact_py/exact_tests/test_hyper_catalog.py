"""Tests for hyper-catalog — regenerate hyper/catalog.ts from /v1/models.

Seams: the pure mapping (API model record -> compact catalog entry), the
regeneration of the CATALOG array inside catalog.ts (surgical splice, rest of
the file untouched), the drift report, and the CLI (mock opener, tmp files,
--check vs write).
"""

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

import _loader

hyper_catalog = _loader.load("hyper-catalog")

# A faithful slice of the live /v1/models response (values seen 2026-09-17):
# glm-5.3-flash is fully in sync with nothing to change, deepseek-v4-pro has
# drifted cost/limits/efforts, and one model with "none"/"minimal" efforts
# exercises vocabulary filtering.
API_PAYLOAD = {
    "data": [
        {
            "id": "glm-5.3-flash",
            "display_name": "GLM 5.3 Flash",
            "context_window": 1048576,
            "max_output_tokens": 131072,
            "capabilities": {"vision": True},
            "reasoning": {
                "effort_levels": [
                    {"value": "low"},
                    {"value": "high"},
                    {"value": "max"},
                ],
                "default_effort_level": "high",
            },
            "pricing": {
                "input": 0.16332,
                "output": 0.5444,
                "cache_create": 0,
                "cache_hit": 0.031575,
            },
        },
        {
            "id": "deepseek-v4-pro",
            "display_name": "DeepSeek V4 Pro (renamed upstream)",
            "context_window": 1000000,
            "max_output_tokens": 384000,
            "capabilities": {"vision": False},
            "reasoning": {
                "effort_levels": [{"value": "high"}, {"value": "xhigh"}],
                "default_effort_level": "high",
            },
            "pricing": {
                "input": 2.4,
                "output": 4.8,
                "cache_create": 0,
                "cache_hit": 0.2,
            },
        },
        {
            "id": "qwen3.7-max",
            "display_name": "Qwen3.7 Max",
            "context_window": 1000000,
            "max_output_tokens": 64000,
            "capabilities": {"vision": False},
            "reasoning": {
                "effort_levels": [
                    {"value": "none"},
                    {"value": "minimal"},
                    {"value": "low"},
                    {"value": "medium"},
                    {"value": "high"},
                ],
                "default_effort_level": "high",
            },
            "pricing": {
                "input": 2.5,
                "output": 7.5,
                "cache_create": 0,
                "cache_hit": 0.5,
            },
        },
    ]
}

# The compact-catalog style the real catalog.ts uses; entry block format is
# the generator's contract with the file.
CATALOG_TS = """/**
 * hyper/catalog.ts — single model-construction seam. (header preserved)
 */

const CATALOG: CompactEntry[] = [
\t{
\t\tid: "glm-5.3-flash", name: "GLM 5.3 Flash", reasoning: true, vision: true,
\t\tefforts: ["low", "high", "max"],
\t\tcost: { input: 0.16, output: 0.54, cacheRead: 0.03, cacheWrite: 0 },
\t\tcontextWindow: 1_048_576, maxTokens: 131_072,
\t},
\t{
\t\tid: "deepseek-v4-pro", name: "DeepSeek V4 Pro", reasoning: true,
\t\tefforts: ["high", "max"],
\t\tcost: { input: 0.8, output: 1.6, cacheRead: 0.16, cacheWrite: 0 },
\t\tcontextWindow: 1_000_000, maxTokens: 384_000,
\t},
];

/** The static catalog, with all invariants applied. */
export function buildModels(): Model<typeof API>[] {
\treturn CATALOG.map(toModel);
}
"""


def api_models():
    return hyper_catalog.parse_api_models(API_PAYLOAD)


class EntryMappingCase(unittest.TestCase):
    def test_maps_pricing_limits_and_vision(self):
        entry = hyper_catalog.entry_from_api(api_models()["glm-5.3-flash"])
        self.assertEqual(entry["id"], "glm-5.3-flash")
        self.assertEqual(entry["name"], "GLM 5.3 Flash")
        self.assertEqual(entry["vision"], True)
        self.assertEqual(
            entry["cost"],
            {"input": 0.16332, "output": 0.5444, "cacheRead": 0.031575, "cacheWrite": 0},
        )
        self.assertEqual(entry["contextWindow"], 1_048_576)
        self.assertEqual(entry["maxTokens"], 131_072)

    def test_efforts_drop_none_and_minimal_and_keep_canonical_order(self):
        entry = hyper_catalog.entry_from_api(api_models()["qwen3.7-max"])
        self.assertEqual(entry["efforts"], ["low", "medium", "high"])

    def test_reasoning_follows_surviving_efforts(self):
        self.assertEqual(hyper_catalog.entry_from_api(api_models()["deepseek-v4-pro"])["reasoning"], True)


class RegenerateCase(unittest.TestCase):
    def test_rewrites_drifted_entries_and_preserves_the_rest(self):
        new_ts = hyper_catalog.regenerate(CATALOG_TS, api_models())
        # everything outside the CATALOG array is byte-identical
        self.assertIn("(header preserved)", new_ts)
        self.assertIn("export function buildModels()", new_ts)
        # drifted entry now carries API values, in the file's compact style
        self.assertIn(
            '\t\tid: "deepseek-v4-pro", name: "DeepSeek V4 Pro", reasoning: true,',
            new_ts,
        )
        self.assertIn('\t\tefforts: ["high", "xhigh"],', new_ts)
        self.assertIn(
            "\t\tcost: { input: 2.4, output: 4.8, cacheRead: 0.2, cacheWrite: 0 },",
            new_ts,
        )
        self.assertIn(
            "\t\tcontextWindow: 1_000_000, maxTokens: 384_000,",
            new_ts,
        )
        # in-sync entry is re-emitted identically (idempotent formatting)
        self.assertIn(
            "\t\tid: \"glm-5.3-flash\", name: \"GLM 5.3 Flash\", reasoning: true, vision: true,",
            new_ts,
        )

    def test_integral_floats_print_bare(self):
        new_ts = hyper_catalog.regenerate(CATALOG_TS, api_models())
        self.assertIn("input: 2.4,", new_ts)
        self.assertNotIn("input: 2.0,", new_ts)


    def test_entries_stay_newline_separated(self):
        new_ts = hyper_catalog.regenerate(CATALOG_TS, api_models())
        self.assertIn("\t},\n\t{\n", new_ts)
        self.assertIn("\t},\n];", new_ts)
        self.assertNotIn("\t},\t{", new_ts)

    def test_curated_display_names_are_preserved(self):
        new_ts = hyper_catalog.regenerate(CATALOG_TS, api_models())
        self.assertIn('name: "DeepSeek V4 Pro",', new_ts)
        self.assertNotIn("renamed upstream", new_ts)
        report = hyper_catalog.diff_catalog(CATALOG_TS, api_models())
        self.assertNotIn("name", [c["field"] for c in report["changes"]])


class ReportCase(unittest.TestCase):
    def test_reports_field_level_drift(self):
        report = hyper_catalog.diff_catalog(CATALOG_TS, api_models())
        changed = {(c["id"], c["field"]): (c["old"], c["new"]) for c in report["changes"]}
        self.assertEqual(changed[("deepseek-v4-pro", "cost.input")], (0.8, 2.4))
        self.assertEqual(changed[("deepseek-v4-pro", "cost.output")], (1.6, 4.8))
        self.assertEqual(changed[("deepseek-v4-pro", "cost.cacheRead")], (0.16, 0.2))
        self.assertEqual(changed[("deepseek-v4-pro", "efforts")], (["high", "max"], ["high", "xhigh"]))

    def test_reports_api_only_models_without_touching_them(self):
        report = hyper_catalog.diff_catalog(CATALOG_TS, api_models())
        self.assertIn("qwen3.7-max", report["api_only"])
        self.assertNotIn("qwen3.7-max", hyper_catalog.regenerate(CATALOG_TS, api_models()))

    def test_models_missing_from_the_api_are_kept_and_reported(self):
        ts = CATALOG_TS.replace(
            '\t{\n\t\tid: "deepseek-v4-pro", name: "DeepSeek V4 Pro", reasoning: true,',
            '\t{\n\t\tid: "retired-model", name: "DeepSeek V4 Pro", reasoning: true,',
        )
        report = hyper_catalog.diff_catalog(ts, api_models())
        self.assertIn("retired-model", report["missing"])
        self.assertIn('id: "retired-model"', hyper_catalog.regenerate(ts, api_models()))

    def test_regeneration_is_idempotent(self):
        once = hyper_catalog.regenerate(CATALOG_TS, api_models())
        twice = hyper_catalog.regenerate(once, api_models())
        self.assertEqual(once, twice)
        self.assertEqual(hyper_catalog.diff_catalog(once, api_models())["changes"], [])


class FakeResponse:
    def __init__(self, payload):
        import io
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CliCase(unittest.TestCase):
    def fake_opener(self, seen):
        def opener(req, timeout=0):
            seen["url"] = req.full_url
            seen["auth"] = req.headers.get("Authorization")
            return FakeResponse(API_PAYLOAD)
        return opener

    def test_fetch_models_sends_bearer_and_parses(self):
        seen = {}
        models = hyper_catalog.fetch_models("k1", opener=self.fake_opener(seen))
        self.assertEqual(seen["url"], hyper_catalog.API_URL)
        self.assertEqual(seen["auth"], "Bearer k1")
        self.assertEqual(models["glm-5.3-flash"]["cost"]["input"], 0.16332)

    def test_api_key_flag_beats_env_beats_auth_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            auth = Path(tmp) / "auth.json"
            auth.write_text(json.dumps({"hyper": {"type": "api", "key": "from-file"}}))
            self.assertEqual(hyper_catalog.resolve_api_key("from-flag", None, auth), "from-flag")
            self.assertEqual(hyper_catalog.resolve_api_key(None, "from-env", auth), "from-env")
            self.assertEqual(hyper_catalog.resolve_api_key(None, None, auth), "from-file")

    def test_check_with_drift_exits_1_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "catalog.ts"
            target.write_text(CATALOG_TS, encoding="utf-8")
            rc = hyper_catalog.main(
                ["--check", "--file", str(target), "--api-key", "k"],
                opener=self.fake_opener({}),
            )
            self.assertEqual(rc, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), CATALOG_TS)

    def test_write_updates_file_then_second_run_is_in_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "catalog.ts"
            target.write_text(CATALOG_TS, encoding="utf-8")
            rc = hyper_catalog.main(
                ["--file", str(target), "--api-key", "k"],
                opener=self.fake_opener({}),
            )
            self.assertEqual(rc, 0)
            written = target.read_text(encoding="utf-8")
            self.assertIn("input: 2.4,", written)
            self.assertNotIn("input: 0.8,", written)
            rc2 = hyper_catalog.main(
                ["--check", "--file", str(target), "--api-key", "k"],
                opener=self.fake_opener({}),
            )
            self.assertEqual(rc2, 0, "second run must report in sync")
