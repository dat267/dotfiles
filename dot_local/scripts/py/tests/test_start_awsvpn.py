import base64
import os
import tempfile
import unittest
import zlib
from unittest import mock

import _loader

vpn = _loader.load("start-awsvpn")


def make_saml_request(request_id="req-123"):
    xml = f'<samlp:Response ID="{request_id}"></samlp:Response>'
    raw_deflate = zlib.compress(xml.encode())[2:-4]
    return base64.b64encode(raw_deflate).decode()


class TestExtractSamlRequestId(unittest.TestCase):
    def test_deflated_saml(self):
        url = "https://idp/login?SAMLRequest=" + make_saml_request("abc-999")
        self.assertEqual(vpn.extract_saml_request_id(url), "abc-999")

    def test_missing_saml(self):
        self.assertIsNone(vpn.extract_saml_request_id("https://idp/login?x=1"))

    def test_garbage_returns_none(self):
        self.assertIsNone(vpn.extract_saml_request_id("https://x/?SAMLRequest=!!!"))


class TestParseOvpnProfile(unittest.TestCase):
    def write_profile(self, lines):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".ovpn", delete=False)
        f.write("\n".join(lines))
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_full_profile(self):
        path = self.write_profile(
            ["# comment", "client", "remote vpn.example.com 443", "proto tcp-client", "nobind"]
        )
        self.assertEqual(
            vpn.parse_ovpn_profile(path), ("vpn.example.com", 443, "tcp")
        )

    def test_defaults(self):
        path = self.write_profile(["client", "remote host.invalid"])
        self.assertEqual(
            vpn.parse_ovpn_profile(path), ("host.invalid", 1194, "udp")
        )

    def test_non_numeric_port_keeps_default(self):
        path = self.write_profile(["remote host abc"])
        self.assertEqual(vpn.parse_ovpn_profile(path)[1], 1194)


class TestPrepareTempConfig(unittest.TestCase):
    def test_strips_nobind(self):
        src = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False)
        src.write("client\nnobind\nremote x 1194\n")
        src.close()
        self.addCleanup(os.remove, src.name)
        out_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(out_dir, ignore_errors=True))
        with mock.patch.object(vpn, "TMP_DIR", out_dir):
            out = vpn.prepare_temp_config(src.name)
        content = open(out).read()
        self.assertNotIn("nobind", content)
        self.assertIn("remote x 1194", content)
        os.remove(out)

    def test_error_falls_back_to_original(self):
        with mock.patch("builtins.open", side_effect=OSError):
            self.assertEqual(vpn.prepare_temp_config("/no/such"), "/no/such")


class TestDetectPaths(unittest.TestCase):
    def test_missing_binaries(self):
        tmp = tempfile.mkdtemp()
        loader, openvpn, dns, base = vpn.detect_paths(tmp)
        self.assertIsNone(loader)
        self.assertIsNone(openvpn)
        self.assertIsNone(dns)
        self.assertEqual(base, tmp)

    def test_present_binaries(self):
        tmp = tempfile.mkdtemp()
        for name in ("ld-musl-x86_64.so.1", "acvc-openvpn", "configure-dns"):
            open(os.path.join(tmp, name), "w").close()
        loader, openvpn, dns, base = vpn.detect_paths(tmp)
        self.assertTrue(loader and openvpn and dns)


if __name__ == "__main__":
    unittest.main()
