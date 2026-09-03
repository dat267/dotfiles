import os
import tempfile
import unittest
from unittest import mock

import _loader

install = _loader.load("install-tools")
uninstall = _loader.load("uninstall-tools")

RELEASES = [
    {
        "tag_name": "v1.0.0",
        "created_at": "2024-01-01T00:00:00Z",
        "assets": [{"name": "other-linux-x86_64", "browser_download_url": "http://x/other"}],
    },
    {
        "tag_name": "max/2024-06-01",
        "created_at": "2024-06-01T00:00:00Z",
        "assets": [
            {
                "name": "toolA-linux-x86_64",
                "browser_download_url": "http://x/toolA-linux-x86_64",
            },
            {
                "name": "toolA-linux-aarch64",
                "browser_download_url": "http://x/toolA-linux-aarch64",
            },
        ],
    },
]


def urlopen_patch(payload):
    resp = mock.Mock()
    resp.read.return_value = payload.encode()
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return mock.patch.object(install.urllib.request, "urlopen", return_value=resp)


class TestUninstallTools(unittest.TestCase):
    def test_removes_matching_binaries(self):
        tmp = tempfile.mkdtemp()
        tool = os.path.join(tmp, "toolA")
        open(tool, "w").close()
        with mock.patch("sys.argv", ["uninstall_tools"]), mock.patch.object(
            uninstall, "INSTALL_DIR", tmp
        ), mock.patch.object(
            uninstall, "get_platform_info", return_value=("linux", "x86_64")
        ), mock.patch.object(uninstall.urllib.request, "urlopen", mock.mock_open(
            read_data=__import__("json").dumps(RELEASES).encode()
        )):
            uninstall.main()
        self.assertFalse(os.path.exists(tool))

    def test_no_match_exits_zero(self):
        releases = [
            {
                "tag_name": "max/2024-06-01",
                "created_at": "2024-06-01T00:00:00Z",
                "assets": [
                    {"name": "toolA-linux-aarch64", "browser_download_url": "http://x/aarch64"}
                ],
            }
        ]
        with mock.patch("sys.argv", ["uninstall_tools"]), mock.patch.object(
            uninstall, "get_platform_info", return_value=("linux", "x86_64")
        ), mock.patch.object(uninstall.urllib.request, "urlopen", mock.mock_open(
            read_data=__import__("json").dumps(releases).encode()
        )):
            with self.assertRaises(SystemExit) as ctx:
                uninstall.main()
            self.assertEqual(ctx.exception.code, 0)


class TestInstallTools(unittest.TestCase):
    def test_installs_matching_asset(self):
        tmp = tempfile.mkdtemp()
        payload = __import__("json").dumps(RELEASES).encode()
        fake_download = mock.mock_open(read_data=payload)
        with mock.patch("sys.argv", ["install_tools"]), mock.patch.object(
            install, "INSTALL_DIR", tmp
        ), mock.patch.object(
            install, "get_platform_info", return_value=("linux", "x86_64")
        ), mock.patch.object(install.urllib.request, "urlopen", fake_download), mock.patch.object(
            install.shutil, "move"
        ) as move:
            install.main()
        # Both assets of the latest max/ release were considered; the
        # matching-suffix one (toolA-linux-x86_64) must be installed.
        dest = os.path.join(tmp, "toolA")
        move.assert_called_once()
        self.assertEqual(move.call_args.args[1], dest)


if __name__ == "__main__":
    unittest.main()
