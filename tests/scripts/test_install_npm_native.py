import base64
import hashlib
import io
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest import mock

import _loader

shared = _loader.load("_shared")
npm = _loader.load("_npm_native")
claude = _loader.load("install_claude")
opencode = _loader.load("install_opencode")

P = shared.Platform


class TestPackageName(unittest.TestCase):
    def test_claude_platforms(self):
        cases = {
            ("linux", "x64", "glibc"): "@anthropic-ai/claude-code-linux-x64",
            ("linux", "arm64", "musl"): "@anthropic-ai/claude-code-linux-arm64-musl",
            ("darwin", "arm64", "glibc"): "@anthropic-ai/claude-code-darwin-arm64",
            ("windows", "x64", "glibc"): "@anthropic-ai/claude-code-win32-x64",
        }
        for (os_name, arch, libc), want in cases.items():
            self.assertEqual(npm.package_name(claude.TOOL, P(os_name, arch), libc), want)

    def test_android_takes_the_linux_glibc_build(self):
        self.assertEqual(npm.package_name(claude.TOOL, P("android", "arm64"), "musl"),
                         "@anthropic-ai/claude-code-linux-arm64")
        self.assertEqual(npm.package_name(opencode.TOOL, P("android", "arm64")),
                         "@opencode/cli-linux-arm64")

    def test_opencode_words_and_baseline(self):
        self.assertEqual(npm.package_name(opencode.TOOL, P("windows", "x64")), "@opencode/cli-windows-x64")
        self.assertEqual(npm.package_name(opencode.TOOL, P("linux", "x64"), "musl", baseline=True),
                         "@opencode/cli-linux-x64-baseline-musl")
        # Baseline builds exist only for x64, and only OpenCode publishes them.
        self.assertEqual(npm.package_name(opencode.TOOL, P("linux", "arm64"), baseline=True),
                         "@opencode/cli-linux-arm64")
        self.assertEqual(npm.package_name(claude.TOOL, P("linux", "x64"), baseline=True),
                         "@anthropic-ai/claude-code-linux-x64")

    def test_unknown_os_raises(self):
        with self.assertRaises(ValueError):
            npm.package_name(claude.TOOL, P("freebsd", "x64"))


class TestHelpers(unittest.TestCase):
    def test_manifest_url_escapes_the_scope_slash(self):
        self.assertEqual(npm.manifest_url("@opencode/cli-linux-arm64"),
                         "https://registry.npmjs.org/@opencode%2Fcli-linux-arm64/latest")
        self.assertTrue(npm.manifest_url("@a/b", "2.1.0").endswith("/@a%2Fb/2.1.0"))

    def test_parse_version(self):
        self.assertEqual(npm.parse_version("2.1.322 (Claude Code)"), "2.1.322")
        self.assertEqual(npm.parse_version("opencode v2.2.7\n"), "2.2.7")
        self.assertEqual(npm.parse_version("1.0.0-beta.3"), "1.0.0-beta.3")
        self.assertIsNone(npm.parse_version("no version"))

    def test_cpu_lacks_avx2(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cpuinfo")
            with open(path, "w") as f:
                f.write("processor : 0\nflags : fpu sse2 avx\n")
            self.assertTrue(npm.cpu_lacks_avx2(path))
            with open(path, "w") as f:
                f.write("flags : fpu avx avx2\n")
            self.assertFalse(npm.cpu_lacks_avx2(path))
            with open(path, "w") as f:
                f.write("Features : fp asimd\n")  # arm64: no flags line
            self.assertFalse(npm.cpu_lacks_avx2(path))
        self.assertFalse(npm.cpu_lacks_avx2("/nonexistent/cpuinfo"))

    def test_verify_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f")
            with open(path, "wb") as f:
                f.write(b"payload")
            good = "sha512-" + base64.b64encode(hashlib.sha512(b"payload").digest()).decode()
            npm.verify_integrity(path, good)
            bad = "sha512-" + base64.b64encode(hashlib.sha512(b"other").digest()).decode()
            with self.assertRaises(RuntimeError):
                npm.verify_integrity(path, bad)
            with self.assertRaises(RuntimeError):
                npm.verify_integrity(path, "md5-abc")

    def test_layout(self):
        lay = npm.layout(claude.TOOL, P("linux", "x64"), home="/h")
        self.assertEqual((lay.binary, lay.launcher), (os.path.join("/h", ".local", "bin", "claude"), None))
        lay = npm.layout(opencode.TOOL, P("windows", "x64"), home="/h")
        self.assertEqual(lay.binary, os.path.join("/h", ".local", "bin", "opencode.exe"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_STATE_HOME", None)
            lay = npm.layout(opencode.TOOL, P("android", "arm64"), home="/h")
        self.assertEqual(lay.binary, os.path.join("/h", ".local", "lib", "opencode-native", "opencode"))
        self.assertEqual(lay.launcher, os.path.join("/h", ".local", "bin", "opencode"))
        self.assertEqual(lay.state, os.path.join("/h", ".local", "state", "opencode-termux"))

    def test_run_argv(self):
        self.assertEqual(npm.run_argv(P("android", "arm64"), "/b"), ["grun", "/b"])
        self.assertEqual(npm.run_argv(P("linux", "x64"), "/b"), ["/b"])

    def test_find_member_and_place(self):
        with tempfile.TemporaryDirectory() as d:
            tgz = os.path.join(d, "p.tgz")
            with tarfile.open(tgz, "w:gz") as tar:
                for name, data in (("package/README.md", b"x"), ("package/bin/opencode", b"new")):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
            with tarfile.open(tgz, "r:gz") as tar:
                member = npm.find_member(tar, "opencode")
                self.assertEqual(member.name, "package/bin/opencode")
                with self.assertRaises(RuntimeError):
                    npm.find_member(tar, "claude")
                tar.extractall(os.path.join(d, "out"), members=[member], filter="data")
            dest = os.path.join(d, "bin", "opencode")
            os.makedirs(os.path.dirname(dest))
            with open(dest, "wb") as f:
                f.write(b"old")
            npm.place(os.path.join(d, "out", member.name), dest)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"new")
            self.assertFalse(os.path.exists(dest + ".new"))
            if os.name == "posix":
                self.assertTrue(os.access(dest, os.X_OK))

    def test_place_on_windows_moves_the_old_binary_aside(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = os.path.join(d, "src"), os.path.join(d, "opencode.exe")
            for path, data in ((src, b"new"), (dest, b"old")):
                with open(path, "wb") as f:
                    f.write(data)
            npm.place(src, dest, windows=True)
            with open(dest + ".old", "rb") as f:
                self.assertEqual(f.read(), b"old")


class TestMain(unittest.TestCase):
    MANIFEST = {"version": "2.0.0", "dist": {"tarball": "https://x/p.tgz", "integrity": "sha512-x"}}

    def run_main(self, tool, argv, have, platform=P("linux", "x64")):
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(npm.Platform, "detect", return_value=platform), \
                mock.patch.object(npm, "fetch_json", return_value=self.MANIFEST), \
                mock.patch.object(npm, "installed_version", return_value=have), \
                mock.patch.object(npm, "download") as download, \
                mock.patch.object(npm, "shutil") as sh, \
                mock.patch.object(npm.os.path, "expanduser", return_value=home):
            sh.which.return_value = "/usr/bin/grun" if platform.is_android else None
            code = npm.main(tool, argv)
            launcher = os.path.join(home, ".local", "bin", tool.name)
            return code, download, os.path.exists(launcher)

    def test_up_to_date_skips_the_download(self):
        code, download, _ = self.run_main(claude.TOOL, [], have="2.0.0")
        self.assertEqual(code, 0)
        download.assert_not_called()

    def test_up_to_date_on_android_refreshes_the_launcher(self):
        code, download, launcher = self.run_main(opencode.TOOL, [], "2.0.0", P("android", "arm64"))
        self.assertEqual(code, 0)
        download.assert_not_called()
        self.assertTrue(launcher)

    def test_check_exit_codes(self):
        self.assertEqual(self.run_main(claude.TOOL, ["--check"], have="2.0.0")[0], 0)
        code, download, _ = self.run_main(claude.TOOL, ["--check"], have="1.9.0")
        self.assertEqual(code, 1)
        download.assert_not_called()

    def test_android_without_grun_fails(self):
        with mock.patch.object(npm.Platform, "detect", return_value=P("android", "arm64")), \
                mock.patch.object(npm.shutil, "which", return_value=None), \
                mock.patch.object(npm, "fetch_json") as fetch:
            self.assertEqual(npm.main(claude.TOOL, []), 1)
            fetch.assert_not_called()

    def test_unresolvable_version_fails(self):
        with mock.patch.object(npm.Platform, "detect", return_value=P("linux", "x64")), \
                mock.patch.object(npm, "fetch_json", return_value=None):
            self.assertEqual(npm.main(claude.TOOL, ["--version", "9.9.9"]), 1)


def _bash():
    return shutil.which("bash") if os.name == "posix" else None


@unittest.skipUnless(_bash(), "needs bash")
class TestLaunchers(unittest.TestCase):
    def layout(self, tool, d):
        return npm.Layout(binary=os.path.join(d, "native", tool.name),
                          launcher=os.path.join(d, "bin", tool.name),
                          state=os.path.join(d, "state"))

    def test_generated_launchers_parse(self):
        with tempfile.TemporaryDirectory() as d:
            for tool in (claude.TOOL, opencode.TOOL):
                text = tool.launcher(tool, self.layout(tool, d), P("android", "arm64"))
                self.assertTrue(text.startswith("#!/"))
                r = subprocess.run([_bash(), "-n"], input=text, text=True, capture_output=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_claude_launcher(self):
        text = claude.launcher(claude.TOOL, self.layout(claude.TOOL, "/x"), P("android", "arm64"))
        self.assertIn("update|upgrade) shift; exec install_claude.py", text)
        self.assertIn("DISABLE_AUTOUPDATER=1", text)
        self.assertIn("exec grun /x/native/claude", text)

    def run_opencode(self, d, args, port):
        """Run the generated launcher with a fake grun that prints its argv."""
        lay = self.layout(opencode.TOOL, d)
        fake = os.path.join(d, "fake")
        os.makedirs(fake, exist_ok=True)
        with open(os.path.join(fake, "grun"), "w") as f:
            f.write('#!/bin/sh\nfor a; do printf "%s\\n" "$a"; done\n')
        os.chmod(os.path.join(fake, "grun"), 0o755)
        script = os.path.join(d, "opencode")
        with open(script, "w") as f:
            f.write(opencode.launcher(opencode.TOOL, lay, P("android", "arm64")))
        env = {**os.environ, "PATH": fake + os.pathsep + os.environ["PATH"],
               "OPENCODE_TERMUX_PORT": str(port), "HOME": d}
        r = subprocess.run([_bash(), script, *args], env=env, capture_output=True, text=True, timeout=60)
        return r, r.stdout.splitlines()[1:]  # drop the binary path

    def listening_port(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        self.addCleanup(srv.close)

        def accept():
            while True:
                try:
                    srv.accept()[0].close()
                except OSError:
                    return
        threading.Thread(target=accept, daemon=True).start()
        return srv.getsockname()[1]

    def test_server_flag_goes_last_or_before_double_dash(self):
        port = self.listening_port()
        url = f"http://127.0.0.1:{port}"
        with tempfile.TemporaryDirectory() as d:
            r, argv = self.run_opencode(d, ["mcp", "list"], port)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(argv, ["mcp", "list", "--server", url])
            self.assertEqual(os.stat(os.path.join(d, "state")).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(os.path.join(d, "state", "password")).st_mode & 0o777, 0o600)
        with tempfile.TemporaryDirectory() as d:
            _, argv = self.run_opencode(d, ["run", "--", "--literal"], port)
            self.assertEqual(argv, ["run", "--server", url, "--", "--literal"])

    def test_passthrough_commands_skip_the_server(self):
        with tempfile.TemporaryDirectory() as d:
            for args in (["serve", "--port", "1"], ["--version"], ["debug", "paths"],
                         ["models", "--server", "http://elsewhere"]):
                r, argv = self.run_opencode(d, args, port=1)
                self.assertEqual(argv, args)
            self.assertFalse(os.path.exists(os.path.join(d, "state")))


@unittest.skipUnless(os.path.isdir("/proc/self"), "needs /proc")
class TestStopServer(unittest.TestCase):
    def test_signals_only_our_server(self):
        with tempfile.TemporaryDirectory() as d:
            lay = npm.Layout(binary=os.path.join(d, "opencode-native", "opencode"), launcher=None, state=d)
            ours = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", lay.binary])
            other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            try:
                pid_file = os.path.join(d, "server.pid")
                with open(pid_file, "w") as f:
                    f.write(str(other.pid))
                self.assertFalse(opencode.stop_server(lay))
                self.assertIsNone(other.poll())
                with open(pid_file, "w") as f:
                    f.write(str(ours.pid))
                self.assertTrue(opencode.stop_server(lay))
                self.assertIsNotNone(ours.wait(timeout=10))
            finally:
                for proc in (ours, other):
                    proc.kill()
                    proc.wait()

    def test_missing_pid_file(self):
        with tempfile.TemporaryDirectory() as d:
            lay = npm.Layout(binary="/x", launcher=None, state=d)
            self.assertFalse(opencode.stop_server(lay))


if __name__ == "__main__":
    unittest.main()
