"""Verify the managed flat Pi theme keeps every panel transparent."""

import json
from pathlib import Path
import unittest

PANEL_TOKENS = [
    "selectedBg",
    "searchMatchBg",
    "userMessageBg",
    "customMessageBg",
    "toolPendingBg",
    "toolSuccessBg",
    "toolErrorBg",
]


class PiFlatThemeTest(unittest.TestCase):
    def setUp(self):
        repo = Path(__file__).resolve().parents[4]
        self.theme = json.loads((repo / "dot_pi/agent/themes/flat.json").read_text())

    def test_every_panel_uses_the_terminal_background(self):
        colors = self.theme["colors"]
        for token in PANEL_TOKENS:
            with self.subTest(token=token):
                self.assertEqual(colors[token], "")

    def test_colors_are_terminal_defaults_or_ansi_slots(self):
        for token, value in self.theme["colors"].items():
            with self.subTest(token=token):
                if value == "":
                    continue
                self.assertIsInstance(value, int)
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 255)

    def test_name_matches_the_settings_choice(self):
        self.assertEqual(self.theme["name"], "flat")
