"""Verify Pi's managed settings preserve user choices while disabling goal."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("chezmoi"), "requires chezmoi")
class PiSettingsTest(unittest.TestCase):
    def test_goal_exclusion_preserves_other_extensions_and_is_idempotent(self):
        repo = Path(__file__).resolve().parents[4]
        template = repo / "dot_pi/agent/modify_settings.json"
        disabled = "-extensions/goal/index.ts"
        selections = ["extensions/custom.ts", "-builtin:mcp", "+extensions/goal/index.ts"]
        with tempfile.TemporaryDirectory() as temp:
            for extensions in (None, selections, [disabled, *selections]):
                with self.subTest(extensions=extensions):
                    settings = {"customPreference": "keep"}
                    if extensions is not None:
                        settings["extensions"] = extensions

                    def render(current):
                        result = subprocess.run(
                            [shutil.which("chezmoi"), "--source", temp,
                             "--destination", temp, "--config", str(Path(temp) / "chezmoi.toml"),
                             "execute-template", "--with-stdin", "--file", str(template)],
                            input=json.dumps(current), capture_output=True, text=True,
                            timeout=10, check=True,
                        )
                        return json.loads(result.stdout.removeprefix("chezmoi:modify-template"))

                    rendered = render(settings)
                    self.assertEqual(rendered.get("extensions"),
                                     (selections if extensions is not None else []) + [disabled])
                    self.assertEqual(rendered["customPreference"], "keep")
                    self.assertEqual(rendered["theme"], "flat")
                    self.assertEqual(render(rendered), rendered)
