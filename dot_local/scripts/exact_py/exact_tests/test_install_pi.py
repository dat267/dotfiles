import os
import unittest
from unittest import mock

import _loader

pi = _loader.load("install-pi")
shared = _loader.load("_shared")

PKG = "@earendil-works/pi-coding-agent"


def proc(stdout="", returncode=0):
    return mock.Mock(stdout=stdout, returncode=returncode, stderr="boom")


def _stem(path):
    """Command name without its directory or Windows launcher extension."""
    base = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".cmd", ".exe", ".bat"):
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


class TestParseNodeVersion(unittest.TestCase):
    def test_typical_output(self):
        self.assertEqual(pi.parse_node_version("v26.9.0\n"), (26, 9, 0))

    def test_patch_zero(self):
        self.assertEqual(pi.parse_node_version("v22.19.0"), (22, 19, 0))

    def test_garbage_is_none(self):
        self.assertIsNone(pi.parse_node_version("command not found"))
        self.assertIsNone(pi.parse_node_version(""))


class TestNodeFloor(unittest.TestCase):
    def test_floor_matches_pi_engines(self):
        self.assertEqual(pi.NODE_FLOOR, (22, 19, 0))

    def test_sufficient(self):
        self.assertTrue(pi.is_sufficient((26, 9, 0)))
        self.assertTrue(pi.is_sufficient((22, 19, 0)))  # exactly the engines floor
        self.assertTrue(pi.is_sufficient((24, 20, 0)))  # Cloud Shell's nvm node

    def test_insufficient(self):
        self.assertFalse(pi.is_sufficient((22, 18, 0)))
        self.assertFalse(pi.is_sufficient((20, 11, 3)))
        self.assertFalse(pi.is_sufficient(None))


class TestCommandConstruction(unittest.TestCase):
    def test_npm_install_is_global_scriptless_and_prefixed(self):
        cmd = pi.npm_install_command("/usr/bin/npm", "/home/u/.local")
        self.assertEqual(
            cmd,
            ["/usr/bin/npm", "install", "-g", "--prefix", "/home/u/.local",
             "--ignore-scripts", PKG])


class TestInstallPrefix(unittest.TestCase):
    """pi installs into a fixed prefix, not npm's node-version-bound global."""

    def test_posix_default_is_local(self):
        self.assertEqual(
            pi.install_prefix(shared.Platform("linux", "x64")),
            os.path.expanduser("~/.local"))

    def test_windows_default_is_apps_pi(self):
        self.assertEqual(
            pi.install_prefix(shared.Platform("windows", "x64")),
            shared.windows_home("Apps", "pi"))

    def test_windows_default_follows_the_windows_profile(self):
        """MSYS2/Cygwin ~ is the emulated home, not the profile the PATH entry
        the PowerShell profile adds lives in."""
        profile = os.path.join(os.sep, "Users", "me")
        with mock.patch.dict(os.environ, {"USERPROFILE": profile}):
            self.assertEqual(pi.install_prefix(shared.Platform("windows", "x64")),
                             os.path.join(profile, "Apps", "pi"))

    def test_explicit_override_expands_tilde(self):
        self.assertEqual(
            pi.install_prefix(shared.Platform("linux", "x64"), "~/custom"),
            os.path.expanduser("~/custom"))


class TestPrefixHelpers(unittest.TestCase):
    def test_under_prefix_posix(self):
        lin = shared.Platform("linux", "x64")
        prefix = os.path.expanduser("~/.local")
        self.assertTrue(pi.under_prefix(os.path.join(prefix, "bin", "pi"), prefix, lin))
        self.assertFalse(pi.under_prefix("/usr/local/bin/pi", prefix, lin))

    def test_under_prefix_windows(self):
        win = shared.Platform("windows", "x64")
        prefix = shared.windows_home("Apps")
        self.assertTrue(pi.under_prefix(os.path.join(prefix, "pi.cmd"), prefix, win))
        self.assertFalse(pi.under_prefix(r"C:\node\pi.cmd", prefix, win))

    def test_path_contains(self):
        prefix = os.path.expanduser("~/.local")
        path_env = os.pathsep.join(["/usr/bin", os.path.join(prefix, "bin")])
        self.assertTrue(pi.path_contains(os.path.join(prefix, "bin"), path_env))

    def test_path_contains_false_when_absent(self):
        self.assertFalse(pi.path_contains(os.path.expanduser("~/.local/bin"), "/usr/bin:/x"))


class TestParsePiVersion(unittest.TestCase):
    def test_bare_semver(self):
        self.assertEqual(pi.parse_pi_version("1.2.3\n"), "1.2.3")

    def test_first_semver_in_noise(self):
        self.assertEqual(pi.parse_pi_version("pi version 2.10.4 (node v26.9.0)\n"), "2.10.4")

    def test_no_version(self):
        self.assertIsNone(pi.parse_pi_version("unknown"))


class FakeRunner:
    """Keyed by (argv[0], argv[1]) with fallthrough defaults for pi/node."""

    def __init__(self, node="v26.9.0", npm_view="3.0.1", pi_version=None,
                 fail_install=False):
        self.calls = []
        self.node = node
        self.npm_view = npm_view
        self.pi_version = pi_version
        self.fail_install = fail_install

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        if cmd[1:3] == ["install", "-g"]:
            if self.fail_install:
                return proc("npm ERR! code EACCES", returncode=1)
            self.pi_version = self.npm_view  # fresh install reports the latest
            return proc("added 1 package in 3s")
        if _stem(cmd[0]) == "node":
            return proc(self.node)
        if _stem(cmd[0]) == "npm":
            return proc(self.npm_view)
        # pi --version before install: only report if a version was seeded
        if self.pi_version:
            return proc(self.pi_version)
        return proc("command not found", returncode=1)


def run_with(which_map, runner, argv=None, plat=None, **runner_kwargs):
    runner = runner if callable(runner) else FakeRunner(**runner_kwargs)
    plat = plat or shared.Platform("linux", "x64")
    shim = pi.global_bin("pi", pi.install_prefix(plat), plat)
    which_map = {"node": "/usr/bin/node", **which_map}

    def which(name):
        # a successful install puts the shim in the prefix, and a pi already
        # there is the installed one — not the PATH copy
        if which_map.get("pi") is None and runner.pi_version:
            if name in (shim, "pi"):
                return shim
        return which_map.get(name)

    with mock.patch.object(pi.shutil, "which", side_effect=which):
        code = pi.main(argv=argv or [], run=runner, plat=plat)
    return code, runner


class TestMain(unittest.TestCase):
    def test_fresh_install(self):
        runner = FakeRunner(pi_version=None)
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": None}, runner)
        self.assertEqual(code, 0)
        install = [c for c in runner.calls if c[1:3] == ["install", "-g"]]
        self.assertEqual(len(install), 1)
        self.assertIn("--ignore-scripts", install[0])
        self.assertIn(PKG, install[0])

    def test_already_latest_skips_install(self):
        runner = FakeRunner(pi_version="3.0.1")
        code, runner = run_with({"npm": "/usr/bin/npm"}, runner)
        self.assertEqual(code, 0)
        self.assertEqual([c for c in runner.calls if c[1:3] == ["install", "-g"]], [])

    def test_outdated_reinstalls(self):
        runner = FakeRunner(pi_version="2.9.0")
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": "/usr/bin/pi"}, runner)
        self.assertEqual(code, 0)
        self.assertEqual(len([c for c in runner.calls if c[1:3] == ["install", "-g"]]), 1)

    def test_force_reinstalls_even_when_current(self):
        runner = FakeRunner(pi_version="3.0.1")
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": "/usr/bin/pi"}, runner, argv=["--force"])
        self.assertEqual(code, 0)
        self.assertEqual(len([c for c in runner.calls if c[1:3] == ["install", "-g"]]), 1)

    def test_check_current_exits_zero_without_install(self):
        runner = FakeRunner(pi_version="3.0.1")
        code, runner = run_with({"npm": "/usr/bin/npm"}, runner, argv=["--check"])
        self.assertEqual(code, 0)
        self.assertEqual([c for c in runner.calls if c[1:3] == ["install", "-g"]], [])

    def test_check_outdated_exits_one_without_install(self):
        runner = FakeRunner(pi_version="2.9.0")
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": "/usr/bin/pi"}, runner, argv=["--check"])
        self.assertEqual(code, 1)
        self.assertEqual([c for c in runner.calls if c[1:3] == ["install", "-g"]], [])

    def test_check_missing_exits_one(self):
        runner = FakeRunner(pi_version=None)
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": None}, runner, argv=["--check"])
        self.assertEqual(code, 1)

    def test_missing_node_exits_before_anything(self):
        runner = FakeRunner(node=None)
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": None}, FakeRunner(node=None))
        self.assertEqual(code, 1)
        self.assertEqual([c for c in runner.calls if c[1:3] == ["install", "-g"]], [])

    def test_old_node_exits_with_pointer(self):
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": None}, FakeRunner(node="v20.11.3"))
        self.assertEqual(code, 1)
        self.assertEqual([c for c in runner.calls if c[1:3] == ["install", "-g"]], [])

    def test_missing_npm_exits_one(self):
        code, runner = run_with({"npm": None, "pi": None}, FakeRunner())
        self.assertEqual(code, 1)

    def test_install_failure_exits_one(self):
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": None},
            FakeRunner(fail_install=True))
        self.assertEqual(code, 1)

    def test_registry_unreachable_still_installs(self):
        # npm view fails (offline mirror, blocked network) — install proceeds;
        # only --check treats the registry as mandatory.
        class DeadRegistry(FakeRunner):
            def __call__(self, cmd):
                if cmd[0].endswith("npm") and cmd[1] == "view":
                    return proc("npm ERR! network", returncode=1)
                return super().__call__(cmd)

        runner = DeadRegistry()
        code, runner = run_with({"npm": "/usr/bin/npm", "pi": None}, runner)
        self.assertEqual(code, 0)
        self.assertEqual(len([c for c in runner.calls if c[1:3] == ["install", "-g"]]), 1)

    def test_install_targets_local_prefix(self):
        runner = FakeRunner(pi_version=None)
        code, runner = run_with({"npm": "/usr/bin/npm", "pi": None}, runner)
        self.assertEqual(code, 0)
        install = [c for c in runner.calls if c[1:3] == ["install", "-g"]][0]
        self.assertEqual(
            install[install.index("--prefix") + 1],
            os.path.expanduser("~/.local"))

    def test_migrates_even_when_path_pi_is_latest(self):
        # A current-but-elsewhere pi (nvm global) must not short-circuit the
        # move into the prefix: the install is a migration, not an update.
        runner = FakeRunner(pi_version="3.0.1")
        code, runner = run_with({"npm": "/usr/bin/npm", "pi": "/usr/bin/pi"}, runner)
        self.assertEqual(code, 0)
        self.assertEqual(len([c for c in runner.calls if c[1:3] == ["install", "-g"]]), 1)

    def test_prefix_shim_resolves_off_path(self):
        """The ~/.local/bin shim is used even when PATH has no pi at all."""
        lin = shared.Platform("linux", "x64")
        shim = os.path.join(os.path.expanduser("~/.local"), "bin", "pi")
        runner = FakeRunner(pi_version=None)

        def which(name):
            table = {"node": "/usr/bin/node", "npm": "/usr/bin/npm"}
            if name == shim and runner.pi_version:
                return shim
            return table.get(name)

        with mock.patch.object(pi.shutil, "which", side_effect=which):
            code = pi.main(argv=[], run=runner, plat=lin)
        self.assertEqual(code, 0)
        self.assertIn(shim, [c[0] for c in runner.calls])


class TestLauncherResolution(unittest.TestCase):
    """Windows ships npm and pi as .cmd shims; PATH probing must ask for them."""

    def test_windows_tries_cmd_shim_first(self):
        win = shared.Platform("windows", "x64")
        self.assertEqual(pi.launcher_names("npm", win), ["npm.cmd", "npm"])

    def test_posix_uses_bare_name(self):
        lin = shared.Platform("linux", "x64")
        self.assertEqual(pi.launcher_names("npm", lin), ["npm"])

    def test_find_launcher_accepts_cmd_shim(self):
        win = shared.Platform("windows", "x64")
        seen = []

        def which(name):
            seen.append(name)
            return r"C:\node\npm.cmd" if name == "npm.cmd" else None

        with mock.patch.object(pi.shutil, "which", side_effect=which):
            self.assertEqual(pi.find_launcher("npm", win), r"C:\node\npm.cmd")
        self.assertEqual(seen, ["npm.cmd"])

    def test_global_bin_windows_is_prefix_root(self):
        win = shared.Platform("windows", "x64")
        self.assertEqual(
            pi.global_bin("pi", r"C:\Users\me\AppData\Roaming\npm", win),
            os.path.join(r"C:\Users\me\AppData\Roaming\npm", "pi.cmd"))

    def test_global_bin_posix_is_prefix_bin(self):
        lin = shared.Platform("linux", "x64")
        # os.path.join, not a literal: the expectation must follow the host's
        # separators, this suite also runs on Windows.
        self.assertEqual(pi.global_bin("pi", "/usr/local", lin),
                         os.path.join("/usr/local", "bin", "pi"))


class TestWindowsMain(unittest.TestCase):
    """End-to-end main() on Windows: .cmd shims, and a shim that lands off PATH."""

    WIN_NPM = r"C:\node\npm.cmd"
    WIN_PREFIX = shared.windows_home("Apps", "pi")

    def _which(self, runner, pi_found=None):
        def which(name):
            table = {
                "node.cmd": None, "node": r"C:\node\node.exe",
                "npm.cmd": self.WIN_NPM, "npm": None,
                "pi.cmd": None, "pi": None,
            }
            if runner.pi_version and name in ("pi.cmd", "pi"):
                return pi_found
            return table.get(name)
        return which

    def test_windows_install_targets_cmd_shim(self):
        win = shared.Platform("windows", "x64")
        runner = FakeRunner(pi_version=None)
        with mock.patch.object(pi.shutil, "which",
                               side_effect=self._which(runner, pi_found=r"C:\node\pi.cmd")):
            code = pi.main(argv=[], run=runner, plat=win)
        self.assertEqual(code, 0)
        install = [c for c in runner.calls if c[1:3] == ["install", "-g"]]
        self.assertEqual(len(install), 1)
        self.assertTrue(install[0][0].endswith("npm.cmd"))
        self.assertEqual(install[0][install[0].index("--prefix") + 1], self.WIN_PREFIX)

    def test_windows_install_targets_apps_prefix(self):
        win = shared.Platform("windows", "x64")
        shim = os.path.join(self.WIN_PREFIX, "pi.cmd")
        runner = FakeRunner(pi_version=None)

        def which(name):
            table = {"node": r"C:\node\node.exe", "npm.cmd": self.WIN_NPM}
            if name == shim and runner.pi_version:
                return shim
            return table.get(name)

        with mock.patch.object(pi.shutil, "which", side_effect=which):
            code = pi.main(argv=[], run=runner, plat=win)
        self.assertEqual(code, 0)
        self.assertIn(shim, [c[0] for c in runner.calls])


if __name__ == "__main__":
    unittest.main()
