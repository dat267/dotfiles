"""Tests for executable_pi_sandbox.py — launch pi under bubblewrap.

The security-relevant decisions are pure: which mode maps to which paths,
which paths are writable, and the exact bwrap argument vector. main() is
exercised with injected execvp/which/probe doubles so no real sandbox runs.

Paths are built from the filesystem root rather than hardcoded POSIX strings:
the same tests run on the Windows CI runner, where abspath turns "/home/u"
into a drive-letter path.
"""
import io
import os
import contextlib
import tempfile
import unittest

import _loader

mod = _loader.load("pi_sandbox")

ROOT = os.path.abspath(os.sep)
HOME = os.path.join(ROOT, "home", "u")


def absp(path):
    return os.path.abspath(path)


def norm(path):
    return os.path.realpath(os.path.abspath(path))


class NormalizeModeTest(unittest.TestCase):
    def test_spellings(self):
        for raw, want in [
            ("ro", "ro"), ("read-only", "ro"), ("READONLY", "ro"),
            ("fa", "fa"), ("full-access", "fa"), ("none", "fa"),
            ("ww", "ww"), ("", "ww"), ("bogus", "ww"), (None, "ww"),
        ]:
            self.assertEqual(mod.normalize_mode(raw), want, raw)


class IsRootTest(unittest.TestCase):
    def test_root_detected(self):
        self.assertTrue(mod.is_root(ROOT))

    def test_subdir_not_root(self):
        self.assertFalse(mod.is_root(os.path.join(HOME, "repos")))


class SubcommandTest(unittest.TestCase):
    def test_detected(self):
        for name in ("install", "remove", "uninstall", "update", "list",
                     "config", "auth", "mcp"):
            self.assertTrue(mod.is_subcommand([name]), name)

    def test_flags_and_empty_are_not_subcommands(self):
        self.assertFalse(mod.is_subcommand([]))
        self.assertFalse(mod.is_subcommand(["--model", "update"]))


class PlanWritableTest(unittest.TestCase):
    def exists_all(self, *_):
        return True

    def test_workspace_writable_in_ww(self):
        ws = os.path.join(HOME, "repos", "proj")
        got = mod.plan_writable(ws, "ww", home=HOME, exists=self.exists_all, env={})
        self.assertIn(norm(ws), got)
        self.assertIn(norm(os.path.join(HOME, ".pi")), got)
        self.assertIn(norm(os.path.join(ROOT, "tmp")), got)

    def test_workspace_not_writable_in_ro(self):
        ws = os.path.join(HOME, "repos", "proj")
        got = mod.plan_writable(ws, "ro", home=HOME, exists=self.exists_all, env={})
        self.assertNotIn(norm(ws), got)
        self.assertIn(norm(os.path.join(HOME, ".pi")), got)

    def test_home_itself_never_writable(self):
        got = mod.plan_writable(os.path.join(HOME, "repos", "proj"), "ww",
                                home=HOME, exists=self.exists_all, env={})
        self.assertNotIn(norm(HOME), got)

    def test_root_refused(self):
        got = mod.plan_writable(ROOT, "ww", extra_rw=[ROOT], home=HOME,
                                exists=self.exists_all, env={})
        self.assertNotIn(norm(ROOT), got)

    def test_nested_duplicate_dropped(self):
        repos = os.path.join(HOME, "repos")
        ws = os.path.join(repos, "proj")
        got = mod.plan_writable(ws, "ww", extra_rw=[repos], home=HOME,
                                exists=self.exists_all, env={})
        self.assertIn(norm(repos), got)
        self.assertNotIn(norm(ws), got)

    def test_sibling_prefix_kept(self):
        ws = os.path.join(HOME, "ws")
        sibling = os.path.join(HOME, "ws2")
        got = mod.plan_writable(ws, "ww", extra_rw=[sibling], home=HOME,
                                exists=self.exists_all, env={})
        self.assertIn(norm(ws), got)
        self.assertIn(norm(sibling), got)

    def test_missing_paths_filtered(self):
        ws = os.path.join(HOME, "repos", "proj")
        present = {absp(os.path.join(HOME, ".pi")), absp(os.path.join(ROOT, "tmp")), absp(ws)}
        got = mod.plan_writable(ws, "ww", home=HOME,
                                exists=lambda p: p in present, env={})
        self.assertEqual(sorted(got), sorted(norm(p) for p in present))

    def test_xdg_dirs_included(self):
        cache = os.path.join(ROOT, "x", "cache")
        data = os.path.join(ROOT, "x", "data")
        got = mod.plan_writable(os.path.join(HOME, "ws"), "ro", home=HOME,
                                exists=self.exists_all, env={"XDG_CACHE_HOME": cache,
                                                             "XDG_DATA_HOME": data})
        self.assertIn(norm(cache), got)
        self.assertIn(norm(data), got)

    def test_pi_state_dirs_included(self):
        agent = os.path.join(ROOT, "x", "agent")
        sessions = os.path.join(ROOT, "x", "sessions")
        got = mod.plan_writable(os.path.join(HOME, "ws"), "ro", home=HOME,
                                exists=self.exists_all,
                                env={"PI_CODING_AGENT_DIR": agent,
                                     "PI_CODING_AGENT_SESSION_DIR": sessions})
        self.assertIn(norm(agent), got)
        self.assertIn(norm(sessions), got)

    def test_known_hosts_writable(self):
        got = mod.plan_writable(os.path.join(HOME, "ws"), "ww", home=HOME,
                                exists=self.exists_all, env={})
        self.assertIn(norm(os.path.join(HOME, ".ssh", "known_hosts")), got)

    def test_aws_caches_writable_but_credentials_read_only(self):
        got = mod.plan_writable(os.path.join(HOME, "ws"), "ww", home=HOME,
                                exists=self.exists_all, env={})
        self.assertIn(norm(os.path.join(HOME, ".aws", "cli", "cache")), got)
        self.assertIn(norm(os.path.join(HOME, ".aws", "sso", "cache")), got)
        self.assertNotIn(norm(os.path.join(HOME, ".aws")), got)
        self.assertNotIn(norm(os.path.join(HOME, ".aws", "config")), got)
        self.assertNotIn(norm(os.path.join(HOME, ".aws", "credentials")), got)


class ConfigRwPathsTest(unittest.TestCase):
    def test_reads_paths_and_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rw")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# extra writable paths\n\n  ~/extra  \n/x/y # trailing\n")
            got = mod.config_rw_paths(env={"PI_SANDBOX_RW_FILE": path})
        self.assertEqual(got, [os.path.expanduser("~/extra"), "/x/y"])

    def test_missing_file_is_empty(self):
        self.assertEqual(mod.config_rw_paths(env={"PI_SANDBOX_RW_FILE": "/no/such/file"}), [])


class BuildArgvTest(unittest.TestCase):
    def test_shape(self):
        argv = mod.build_bwrap_argv(
            "/usr/bin/bwrap", "/usr/bin/pi", ["-c", "hi"],
            "/home/u/proj", ["/home/u/proj", "/home/u/.pi", "/tmp"],
        )
        self.assertEqual(argv[0], "/usr/bin/bwrap")
        joined = " ".join(argv)
        self.assertIn("--ro-bind / /", joined)
        self.assertIn("--dev /dev", joined)
        self.assertIn("--proc /proc", joined)
        self.assertIn("--die-with-parent", joined)
        self.assertIn("--chdir /home/u/proj", joined)
        self.assertIn("--setenv PWD /home/u/proj", joined)
        self.assertEqual(argv.count("--bind-try"), 3)
        # pi + its args come after the "--" terminator, marker set before it.
        sep = argv.index("--")
        self.assertEqual(argv[sep + 1:], ["/usr/bin/pi", "-c", "hi"])
        self.assertEqual(argv[argv.index("PI_BWRAP") - 1], "--setenv")

    def test_ssh_config_dir_masked(self):
        argv = mod.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                    "/home/u/proj", [], "/etc/ssh/ssh_config.d")
        at = argv.index("--tmpfs")
        self.assertEqual(argv[at:at + 2], ["--tmpfs", "/etc/ssh/ssh_config.d"])

    def test_no_ssh_tmpfs_when_unset(self):
        argv = mod.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                    "/home/u/proj", [])
        self.assertNotIn("--tmpfs", argv)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.ws = os.getcwd()
        self.calls = []

        def execvp(file, args):
            self.calls.append((file, list(args)))

        self.execvp = execvp

    def run_main(self, argv=None, env=None, **over):
        kwargs = dict(
            env=env if env is not None else {},
            execvp=self.execvp,
            which=lambda name: {"pi": "/usr/bin/pi", "bwrap": "/usr/bin/bwrap"}.get(name),
            exists=lambda p: True,
            isdir=lambda p: True,
            probe=lambda bwrap: True,
            is_linux=True,
        )
        kwargs.update(over)
        return mod.main(argv if argv is not None else [], **kwargs)

    def base_env(self, **extra):
        env = {"PI_SANDBOX_WORKSPACE": self.ws}
        env.update(extra)
        return env

    def test_sandbox_execs_bwrap(self):
        rc = self.run_main(env=self.base_env())
        self.assertEqual(rc, 127)  # execvp double returns
        self.assertEqual(len(self.calls), 1)
        file, args = self.calls[0]
        self.assertEqual(file, "/usr/bin/bwrap")
        self.assertIn("--ro-bind", args)
        self.assertIn(absp(self.ws), args)

    def test_fa_runs_pi_directly(self):
        self.run_main(env=self.base_env(PI_SANDBOX_MODE="fa"))
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_disable_runs_pi_directly(self):
        self.run_main(env=self.base_env(PI_SANDBOX_DISABLE="1"))
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_nested_marker_runs_pi_directly(self):
        self.run_main(env=self.base_env(PI_BWRAP="1"))
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_non_linux_falls_back(self):
        self.run_main(env=self.base_env(), is_linux=False)
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_missing_bwrap_falls_back(self):
        self.run_main(env=self.base_env(), which=lambda name: "/usr/bin/pi" if name == "pi" else None)
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_probe_failure_falls_back(self):
        self.run_main(env=self.base_env(), probe=lambda bwrap: False)
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_missing_pi_is_127(self):
        rc = self.run_main(env=self.base_env(), which=lambda name: None)
        self.assertEqual(rc, 127)
        self.assertEqual(self.calls, [])

    def test_root_workspace_falls_back(self):
        self.run_main(env={"PI_SANDBOX_WORKSPACE": ROOT})
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")

    def test_missing_workspace_is_2(self):
        rc = self.run_main(env={"PI_SANDBOX_WORKSPACE": os.path.join(ROOT, "does", "not", "exist")},
                           exists=lambda p: False, isdir=lambda p: False)
        self.assertEqual(rc, 2)
        self.assertEqual(self.calls, [])

    def test_dry_run_prints_command(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.run_main(env=self.base_env(PI_SANDBOX_DRY_RUN="1"))
        self.assertEqual(rc, 0)
        self.assertEqual(self.calls, [])
        self.assertIn("/usr/bin/bwrap", buf.getvalue())
        self.assertIn("--ro-bind / /", buf.getvalue())

    def test_extra_rw_paths_bound(self):
        one = os.path.join(ROOT, "extra", "one")
        two = os.path.join(ROOT, "extra", "two")
        self.run_main(env=self.base_env(PI_SANDBOX_RW=one + os.pathsep + two))
        _, args = self.calls[0]
        self.assertIn(norm(one), args)
        self.assertIn(norm(two), args)

    def test_config_file_paths_bound(self):
        extra = os.path.join(ROOT, "cfg", "extra")
        with tempfile.TemporaryDirectory() as tmp:
            rw = os.path.join(tmp, "rw")
            with open(rw, "w", encoding="utf-8") as handle:
                handle.write(extra + "\n")
            env = self.base_env(PI_SANDBOX_RW_FILE=rw)
            self.run_main(env=env)
        _, args = self.calls[0]
        self.assertIn(norm(extra), args)

    def test_ssh_config_dir_masked(self):
        self.run_main(env=self.base_env())
        _, args = self.calls[0]
        at = args.index("--tmpfs")
        self.assertEqual(args[at:at + 2], ["--tmpfs", mod.SSH_CONFIG_DIR])

    def test_pi_args_passed_through(self):
        self.run_main(env=self.base_env(), argv=["-c", "hello world"])
        _, args = self.calls[0]
        self.assertEqual(args[args.index("--") + 1:], ["/usr/bin/pi", "-c", "hello world"])

    def test_normal_launch_sandboxes_without_continue(self):
        self.run_main(env=self.base_env(), argv=["--model", "x"])
        _, args = self.calls[0]
        self.assertEqual(args[args.index("--") + 1:], ["/usr/bin/pi", "--model", "x"])

    def test_update_runs_pi_directly(self):
        self.run_main(env=self.base_env(), argv=["update"])
        self.assertEqual(self.calls[0][0], "/usr/bin/pi")
        self.assertEqual(self.calls[0][1], ["/usr/bin/pi", "update"])

    def test_install_runs_pi_directly(self):
        self.run_main(env=self.base_env(), argv=["install", "npm:foo"])
        self.assertEqual(self.calls[0][1], ["/usr/bin/pi", "install", "npm:foo"])


if __name__ == "__main__":
    unittest.main()
