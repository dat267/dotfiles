"""The ssh config must verify host keys, except on the tailnet aliases.

The wildcard block used to disable verification for every host, which also made
the sandbox's writable ~/.ssh/known_hosts pointless: nothing was ever recorded.
"""
import unittest

import _loader

CONFIG = _loader.SOURCE / "private_dot_ssh" / "private_config"
ALIASES = ("nexus", "citadel", "outpost")


def blocks():
    """{host patterns: {directive: value}} for each Host section."""
    sections, current = {}, None
    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        if key.lower() == "host":
            current = sections.setdefault(tuple(value.split()), {})
        elif current is not None:
            current[key.lower()] = value.strip()
    return sections


class TestSshConfig(unittest.TestCase):
    def test_the_wildcard_block_accepts_new_keys_and_keeps_known_hosts(self):
        wildcard = blocks()[("*",)]
        self.assertEqual(wildcard["stricthostkeychecking"], "accept-new")
        self.assertNotIn("userknownhostsfile", wildcard)

    def test_the_tailnet_aliases_skip_verification(self):
        sections = blocks()
        relaxed = [hosts for hosts, values in sections.items() if values.get("stricthostkeychecking") == "no"]
        self.assertEqual(len(relaxed), 1, "verification is skipped in exactly one block")
        self.assertEqual(sorted(relaxed[0]), sorted(ALIASES))
        self.assertEqual(sections[relaxed[0]]["userknownhostsfile"], "/dev/null")

    def test_every_alias_still_names_its_host(self):
        sections = blocks()
        self.assertEqual(sections[("nexus",)]["user"], "root")
        for alias in ("citadel", "outpost"):
            self.assertEqual(sections[(alias,)]["user"], "dat")
            self.assertTrue(sections[(alias,)]["hostname"].startswith("100.64.0."))
