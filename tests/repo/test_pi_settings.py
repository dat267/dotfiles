"""Verify Pi's managed settings preserve user choices without retired entries."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import _loader


@unittest.skipUnless(shutil.which("chezmoi"), "requires chezmoi")
class PiSettingsTest(unittest.TestCase):
    def test_retired_goal_exclusion_is_removed_and_is_idempotent(self):
        repo = _loader.SOURCE
        template = repo / "dot_pi/private_agent/modify_private_settings.json"
        retired = "-extensions/goal/index.ts"
        selections = ["extensions/custom.ts", "-builtin:mcp"]
        cases = [
            (None, None),
            (selections, selections),
            ([retired, *selections], selections),
            ([retired], None),
        ]
        with tempfile.TemporaryDirectory() as temp:
            for extensions, expected in cases:
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
                    self.assertEqual(rendered.get("extensions"), expected)
                    self.assertEqual(rendered["customPreference"], "keep")
                    self.assertEqual(rendered["theme"], "flat", "the managed theme is selected, not left to the terminal")
                    self.assertEqual(render(rendered), rendered)

    def test_retired_claude_code_package_is_dropped_and_the_users_stay(self):
        repo = _loader.SOURCE
        template = repo / "dot_pi/private_agent/modify_private_settings.json"
        source = "https://github.com/earendil-works/pi-claude-code"
        cases = [
            # A declaration an earlier apply wrote must not survive, in either form.
            ([source], None),
            ([{"source": source, "autoload": False}], None),
            (["npm:elsewhere", source], ["npm:elsewhere"]),
            (["npm:elsewhere"], ["npm:elsewhere"]),
            (None, None),
        ]
        with tempfile.TemporaryDirectory() as temp:
            for packages, expected in cases:
                with self.subTest(packages=packages):
                    settings = {} if packages is None else {"packages": packages}

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
                    self.assertEqual(rendered.get("packages"), expected)
                    self.assertEqual(render(rendered), rendered)
