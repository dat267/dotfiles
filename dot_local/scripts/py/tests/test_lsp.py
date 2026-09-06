import pathlib
import re
import tempfile
import unittest
from unittest import mock

import _loader

lsp = _loader.load("lsp")
shared = _loader.load("_shared")


class TestGetPlatform(unittest.TestCase):
    def detect(self, system, machine, termux=False, termux_root=False):
        env = {"TERMUX_VERSION": "1"} if termux else {}
        # Patch the /data/data/com.termux path check too — it is real when the
        # suite runs inside Termux and would otherwise leak into the result.
        with mock.patch("platform.system", return_value=system), mock.patch(
            "platform.machine", return_value=machine
        ), mock.patch.dict("os.environ", env, clear=False), mock.patch(
            "os.path.exists", return_value=termux_root
        ):
            import os

            saved = None
            if not termux:
                saved = os.environ.pop("TERMUX_VERSION", None)
            try:
                return lsp.get_platform()
            finally:
                if saved is not None:
                    os.environ["TERMUX_VERSION"] = saved

    def test_linux_x64(self):
        self.assertEqual(self.detect("Linux", "x86_64"), ("linux", "x64"))

    def test_linux_arm64(self):
        self.assertEqual(self.detect("Linux", "aarch64"), ("linux", "arm64"))

    def test_termux_is_android(self):
        self.assertEqual(
            self.detect("Linux", "aarch64", termux=True),
            ("android", "arm64"),
        )

    def test_termux_via_root_path(self):
        # Second detection branch: env var absent, Termux root path exists.
        self.assertEqual(self.detect("Linux", "x86_64", termux_root=True), ("android", "x64"))

    def test_windows(self):
        self.assertEqual(self.detect("Windows", "AMD64"), ("windows", "x64"))


class TestCreateProxy(unittest.TestCase):
    def test_unix_proxy(self):
        import os
        import tempfile

        with mock.patch.object(lsp, "BIN_DIR", tempfile.mkdtemp()):
            target = "/opt/tool/bin/serve"
            lsp.create_proxy(target, "serve")
            proxy = os.path.join(lsp.BIN_DIR, "serve")
            try:
                content = open(proxy).read()
                self.assertIn(f'exec "{target}" "$@"', content)
                self.assertTrue(os.access(proxy, os.X_OK))
            finally:
                os.remove(proxy)


class TestExtractArchive(unittest.TestCase):
    def test_tar_gz(self):
        import os
        import tarfile
        import tempfile

        src = os.path.join(tempfile.mkdtemp(), "a.tar.gz")
        dest = tempfile.mkdtemp()
        with tarfile.open(src, "w:gz") as t:
            data = os.path.join(tempfile.mkdtemp(), "x.txt")
            open(data, "w").write("hi")
            t.add(data, arcname="x.txt")
        lsp.extract_archive(src, dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "x.txt")))

    def test_zip(self):
        import os
        import tempfile
        import zipfile

        src = os.path.join(tempfile.mkdtemp(), "a.zip")
        dest = tempfile.mkdtemp()
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("y.txt", "yo")
        lsp.extract_archive(src, dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "y.txt")))


# get_latest_github_version moved to _shared.github_latest_tag;
# covered in tests/test_shared.py (TestGithubLatestTag).
# extract_archive moved to _shared.extract_archive;
# covered in tests/test_shared.py (TestExtractArchive).


class TestLspDeduplication(unittest.TestCase):
    """lsp.py must not carry copies of _shared helpers."""

    def test_uses_shared_extract_archive(self):
        import inspect

        self.assertNotIn("def extract_archive", inspect.getsource(lsp))

    def test_marksman_uses_install_helper(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(
            lsp, "BIN_DIR", d
        ), mock.patch.object(lsp, "install_github_release_binary") as helper:
            lsp.install_marksman("linux", "x64")
        helper.assert_called_once_with(
            "https://github.com/artempyanykh/marksman/releases/latest/download/marksman-linux-x64",
            "marksman",
            d,
        )

    def test_marksman_skips_when_already_installed(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "marksman").write_text("x")
            with mock.patch.object(lsp, "BIN_DIR", d), mock.patch.object(
                lsp, "install_github_release_binary"
            ) as helper:
                lsp.install_marksman("linux", "x64")
        helper.assert_not_called()


class TestServerManifest(unittest.TestCase):
    """Single source of truth for the LSP server set: lsp-servers.json.

    Both lsp.py (install recipes) and lsp.lua (editor configs) derive from
    it. These tests pin the cross-file agreement so the lists cannot drift.
    """

    def setUp(self):
        import json
        import pathlib

        root = pathlib.Path(_loader.PY_DIR).parent.parent.parent  # repo root
        self.root = root
        manifest_path = root / "dot_config/nvim/lsp-servers.json"
        self.manifest = json.loads(manifest_path.read_text())
        self.lua = (root / "dot_config/nvim/lua/lsp.lua").read_text()

    def server_blocks(self):
        """Map server name -> config block text from lsp.lua's servers table."""
        servers_table = re.search(r"^local servers = \{(.*?)^\}", self.lua, re.S | re.M)
        self.assertIsNotNone(servers_table, "local servers table not found in lsp.lua")
        blocks = {}
        for m in re.finditer(r"^  (\w+) = \{(.*?)^  \},", servers_table.group(1), re.S | re.M):
            blocks[m.group(1)] = m.group(2)
        return blocks

    def test_manifest_has_editor_servers_with_binary_and_recipe(self):
        for name, entry in self.manifest.items():
            with self.subTest(server=name):
                self.assertIn("install", entry, f"{name} missing install recipe")
                if entry.get("editor", True):
                    self.assertTrue(entry.get("binary"), f"{name} missing binary")

    def test_every_lua_server_is_in_manifest_and_binary_matches(self):
        blocks = self.server_blocks()
        for name, block in blocks.items():
            with self.subTest(server=name):
                self.assertIn(name, self.manifest, f"{name} configured in lsp.lua but absent from manifest")
                binary = self.manifest[name].get("binary")
                cmd = re.search(r'cmd = \{ "([^"]+)"', block)
                if cmd and binary:
                    self.assertEqual(cmd.group(1), binary, f"{name}: lsp.lua cmd[0] != manifest binary")

    def test_every_manifest_editor_server_has_lua_config(self):
        blocks = self.server_blocks()
        for name, entry in self.manifest.items():
            if entry.get("editor", True):
                self.assertIn(name, blocks, f"{name} in manifest but unconfigured in lsp.lua")

    def test_recipes_cover_all_install_keys(self):
        recipes = set(lsp.INSTALL_RECIPES)
        for name, entry in self.manifest.items():
            self.assertIn(entry["install"], recipes, f"{name}: recipe '{entry['install']}' has no installer")

    def test_node_manifest_binaries_are_installed_by_node_recipe(self):
        node_installed = [
            e["binary"] for e in self.manifest.values()
            if e.get("binary") and e["install"] == "node"
        ]
        for binary in node_installed:
            self.assertIn(binary, lsp.NPM_BINS, f"{binary} not produced by the node recipe")


if __name__ == "__main__":
    unittest.main()
