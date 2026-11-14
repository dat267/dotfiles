"""Verify the managed flat Pi theme keeps every panel transparent."""

import json
from pathlib import Path
import unittest

import _loader

# Panels that stay on the terminal background, which is what keeps the theme
# flat. Selection and search are not panels: they mark a row the user is acting
# on, so they carry a background of their own and are checked separately.
PANEL_TOKENS = [
    "userMessageBg",
    "customMessageBg",
    "toolPendingBg",
    "toolSuccessBg",
    "toolErrorBg",
]


class PiFlatThemeTest(unittest.TestCase):
    def setUp(self):
        repo = _loader.SOURCE
        self.theme = json.loads((repo / "dot_pi/private_agent/themes/flat.json").read_text())

    def test_every_panel_uses_the_terminal_background(self):
        colors = self.theme["colors"]
        for token in PANEL_TOKENS:
            with self.subTest(token=token):
                self.assertEqual(colors[token], "")

    def test_selection_and_search_are_visible(self):
        colors = self.theme["colors"]
        for token in ("selectedBg", "searchMatchBg"):
            with self.subTest(token=token):
                self.assertIsInstance(colors[token], int, "an empty value is the terminal background, so the mark disappears")
                self.assertGreaterEqual(colors[token], 16, "16-255 only: 0-15 follow the terminal's own palette")

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
