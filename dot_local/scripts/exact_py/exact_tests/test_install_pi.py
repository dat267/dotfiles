import unittest
from unittest import mock

import _loader

pi = _loader.load("install-pi")

PKG = "@earendil-works/pi-coding-agent"


def proc(stdout="", returncode=0):
    return mock.Mock(stdout=stdout, returncode=returncode, stderr="boom")


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
    def test_npm_install_is_global_and_scriptless(self):
        cmd = pi.npm_install_command("/usr/bin/npm")
        self.assertEqual(cmd, ["/usr/bin/npm", "install", "-g", "--ignore-scripts", PKG])


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
        if cmd[0].endswith("node"):
            return proc(self.node)
        if cmd[0].endswith("npm"):
            return proc(self.npm_view)
        # pi --version before install: only report if a version was seeded
        if self.pi_version:
            return proc(self.pi_version)
        return proc("command not found", returncode=1)


def run_with(which_map, runner, argv=None, **runner_kwargs):
    runner = runner if callable(runner) else FakeRunner(**runner_kwargs)
    which_map = {"node": "/usr/bin/node", **which_map}

    def which(name):
        # a successful `npm install -g` puts the pi shim on PATH
        if name == "pi" and which_map.get("pi") is None and runner.pi_version:
            return "/usr/bin/pi"
        return which_map.get(name)

    with mock.patch.object(pi.shutil, "which", side_effect=which):
        code = pi.main(argv=argv or [], run=runner)
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
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": "/usr/bin/pi"}, runner)
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
        code, runner = run_with(
            {"npm": "/usr/bin/npm", "pi": "/usr/bin/pi"}, runner, argv=["--check"])
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


if __name__ == "__main__":
    unittest.main()
