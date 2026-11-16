"""Verify the models.json cap: every catalogued model over 256k is held at 256k."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import _loader

MODEL_CAP = 262_144


@unittest.skipUnless(shutil.which("chezmoi"), "requires chezmoi")
class RenderMixin:
    """Render the real template through chezmoi, as apply does."""

    def setUp(self):
        self.template = _loader.SOURCE / "dot_pi/private_agent/modify_private_models.json"

    def render(self, current):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [shutil.which("chezmoi"), "--source", temp, "--destination", temp,
                 "--config", str(Path(temp) / "chezmoi.toml"),
                 "execute-template", "--with-stdin", "--file", str(self.template)],
                input=json.dumps(current), capture_output=True, text=True,
                timeout=10, check=True,
            )
        return json.loads(result.stdout.removeprefix("chezmoi:modify-template"))

    def caps(self, rendered):
        """Flatten to {"provider/model": contextWindow}."""
        return {
            f"{provider}/{model}": value["contextWindow"]
            for provider, entry in rendered["providers"].items()
            for model, value in entry.get("modelOverrides", {}).items()
        }


@unittest.skipUnless(shutil.which("chezmoi"), "requires chezmoi")
class ModelsCapTest(RenderMixin, unittest.TestCase):
    def test_every_id_is_capped_at_256k(self):
        caps = self.caps(self.render({}))
        self.assertTrue(caps, "the cap list is empty")
        for key, cap in caps.items():
            with self.subTest(model=key):
                self.assertEqual(cap, MODEL_CAP)

    def test_user_providers_are_preserved_and_rendering_is_idempotent(self):
        current = {"providers": {"mine": {"modelOverrides": {"x": {"contextWindow": 1234}}}}}
        rendered = self.render(current)
        self.assertEqual(
            rendered["providers"]["mine"]["modelOverrides"]["x"]["contextWindow"], 1234)
        self.assertEqual(self.render(rendered), rendered)


@unittest.skipUnless(shutil.which("chezmoi"), "requires chezmoi")
class CatalogCoverageTest(RenderMixin, unittest.TestCase):
    """Every model the in-repo catalogs advertise above the cap must be listed.

    The list is maintained by hand, so a catalog that gains a 300k or 512k
    model was silently left at its advertised window: at a 500k cap that was
    a rounding error, at 256k it is twice the intended size.
    """

    CATALOGS = ("hyper", "cline-pass", "commandcode")

    def catalogued(self):
        """{provider: {id: contextWindow}} for every entry above the cap."""
        found = {}
        for provider in self.CATALOGS:
            path = (_loader.SOURCE / "dot_pi/private_agent/exact_extensions"
                    / "exact_providers" / provider / "catalog.ts")
            text = path.read_text()
            entries = {}
            for match in re.finditer(r'id:\s*"([^"]+)"(.*?)\n\t\}', text, re.S):
                window = re.search(r"contextWindow:\s*([\d_]+)", match.group(2))
                if window:
                    value = int(window.group(1).replace("_", ""))
                    if value > MODEL_CAP:
                        entries[match.group(1)] = value
            found[provider] = entries
        return found

    def test_every_catalogued_model_above_the_cap_is_listed(self):
        caps = self.caps(self.render({}))
        checked = 0
        for provider, entries in self.catalogued().items():
            self.assertTrue(entries, f"no {provider} model parsed out of its catalog")
            for model in entries:
                checked += 1
                with self.subTest(provider=provider, model=model):
                    key = f"{provider}/{model}"
                    self.assertIn(key, caps, f"{key} advertises more than the cap but is not listed")
                    self.assertEqual(caps[key], MODEL_CAP)
        self.assertGreater(checked, 50)
