"""Every installer network read must carry a timeout.

A urlopen without one blocks until TCP gives up, which on a blackholed link can
be tens of minutes: the installer looks hung with nothing on screen. The rest of
the network code (_shared.fetch_json, _shared.download, install_pi) already
bounds its reads, so these call sites are the exception, not the rule.
"""
import json
import unittest
from unittest import mock

import _loader

go = _loader.load("install_go")
tf = _loader.load("install_terraform")
sdk = _loader.load("install_android_sdk")
nf = _loader.load("install_nerd_font")


class Recorder:
    """urlopen double that records its keyword arguments and replays a payload."""

    def __init__(self, payload=b""):
        self.payload = payload
        self.calls = []

    class _Response:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def __call__(self, request, *args, **kwargs):
        self.calls.append(kwargs)
        return self._Response(self.payload)

    def assertAllTimed(self, test):
        test.assertTrue(self.calls, "urlopen was never called")
        for kwargs in self.calls:
            test.assertIn("timeout", kwargs, "this network read has no timeout")
            test.assertGreater(kwargs["timeout"], 0)


class InstallerNetworkTimeoutTest(unittest.TestCase):
    def test_go_version_fetch_is_bounded(self):
        rec = Recorder(b"go1.24.1\ntime 2024-01-01\n")
        with mock.patch.object(go.urllib.request, "urlopen", rec):
            self.assertEqual(go.fetch_latest_go_version(), "go1.24.1")
        rec.assertAllTimed(self)

    def test_terraform_index_fetch_is_bounded(self):
        rec = Recorder(json.dumps({"terraform": {"versions": {"1.9.0": {}}}}).encode())
        with mock.patch.object(tf.urllib.request, "urlopen", rec):
            self.assertEqual(tf.fetch_latest_version(), "1.9.0")
        rec.assertAllTimed(self)

    def test_android_repository_fetch_is_bounded(self):
        rec = Recorder(b"<sdk-repository></sdk-repository>")
        with mock.patch.object(sdk.urllib.request, "urlopen", rec):
            self.assertEqual(sdk.fetch_repository_xml(), b"<sdk-repository></sdk-repository>")
        rec.assertAllTimed(self)

    def test_android_cmdline_url_resolution_is_bounded(self):
        rec = Recorder(b"<sdk-repository></sdk-repository>")
        with mock.patch.object(sdk.urllib.request, "urlopen", rec):
            with self.assertRaises(SystemExit):
                sdk.resolve_cmdline_url("linux")
        rec.assertAllTimed(self)

    def test_nerd_font_download_is_bounded(self):
        rec = Recorder(b"not a zip")
        with mock.patch.object(nf.urllib.request, "urlopen", rec):
            with self.assertRaises(Exception):
                with nf.extracted_fonts("Hack"):
                    pass
        rec.assertAllTimed(self)



