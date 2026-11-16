"""Verify the models.json cap: every catalogued 1M model is held at 256k."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import _loader

MODEL_CAP = 262_144


@unittest.skipUnless(shutil.which("chezmoi"), "requires chezmoi")
class ModelsCapTest(unittest.TestCase):
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
