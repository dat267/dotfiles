"""Consistency seam: yazi config references vs py scripts.

Every `scripts/py/<name>` reference in the yazi configs must resolve to a
script in the chezmoi source. The reverse is NOT asserted — standalone
tools (sysinfo, dotfiles, yazi-rename, installers) are invoked manually.
"""

import pathlib
import re
import unittest

import _loader

PY_DIR = pathlib.Path(_loader.PY_DIR)
REPO_ROOT = PY_DIR.parents[2]  # .../chezmoi
YAZI_CONFIGS = [
    REPO_ROOT / "dot_config" / "yazi" / "keymap.toml",
    REPO_ROOT / "dot_config" / "yazi" / "yazi.toml",
]

# `scripts/py/yazi-x.py` with either slash flavor; captures the file name.
REF_RE = re.compile(r"scripts[/\\]py[/\\]([\w.-]+)")


def referenced_scripts():
    refs = {}
    for config in YAZI_CONFIGS:
        text = config.read_text()
        for name in REF_RE.findall(text):
            refs.setdefault(name, []).append(config.name)
    return refs


def script_exists(name):
    candidates = [
        PY_DIR / f"executable_{name}",
        PY_DIR / f"executable_{name.replace('-', '_')}",
    ]
    return any(c.exists() for c in candidates)


class TestYaziConfigReferencesScripts(unittest.TestCase):
    def test_configs_exist(self):
        for config in YAZI_CONFIGS:
            self.assertTrue(config.exists(), f"missing yazi config: {config}")

    def test_every_referenced_script_exists(self):
        refs = referenced_scripts()
        self.assertTrue(refs, "no references found — regex or config path drifted")
        missing = {name: files for name, files in refs.items() if not script_exists(name)}
        self.assertEqual(missing, {}, "yazi config references missing py scripts")

    def test_known_bindings_present(self):
        """Pin the expected set so a wholesale config rewrite can't silently
        drop references and still pass the existence check above."""
        refs = referenced_scripts()
        for expected in (
            "yazi-compress.py",
            "yazi-extract.py",
            "yazi-ffmpeg-concat.py",
            "yazi-ffmpeg-split.py",
            "yazi-ffmpeg-streams.py",
            "yazi-ffmpeg-transcode.py",
            "yazi-translate.py",
        ):
            self.assertIn(expected, refs)


if __name__ == "__main__":
    unittest.main()
