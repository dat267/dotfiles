"""Tests for _sandbox.py — the shared bubblewrap launcher behind pi and pier.

The security-relevant decisions are pure: which mode maps to which paths,
which paths are writable, and the exact bwrap argument vector. main() is
exercised with injected execvp/which/probe doubles so no real sandbox runs.

Every tool declares a Profile, so the shared behavior is asserted for both
real profiles and a synthetic one proves the profile — not the tool script —
drives the per-tool parts (subcommands, agent-state vars, env var names).

Paths are built from the filesystem root rather than hardcoded POSIX strings:
the same tests run on the Windows CI runner, where abspath turns "/home/u"
into a drive-letter path.
"""
import contextlib
import io
import os
import tempfile
import unittest

import _loader

sandbox = _loader.load("_sandbox")
pi_sandbox = _loader.load("pi_sandbox")
pier_sandbox = _loader.load("pier_sandbox")

ROOT = os.path.abspath(os.sep)
HOME = os.path.join(ROOT, "home", "u")

# The two real profiles plus one synthetic profile that shares nothing with
# them, so a test that passes for all three is testing the module, not a tool.
OTHER = sandbox.Profile(
    tool="tool",
    env_prefix="TOOLX",
    subcommands=("frobnicate",),
    agent_dir_vars=("TOOLX_AGENT_DIR",),
    remote_sockets=(("TOOLX_SERVICE", os.path.join("toolx", "toolx.sock")),),
)
PROFILES = {"pi": pi_sandbox.PROFILE, "pier": pier_sandbox.PROFILE, "other": OTHER}


def absp(path):
    return os.path.abspath(path)


def norm(path):
    return os.path.realpath(os.path.abspath(path))


class ProfileTest(unittest.TestCase):
    def test_var_builds_the_tool_env_namespace(self):
        self.assertEqual(OTHER.var("MODE"), "TOOLX_SANDBOX_MODE")
        self.assertEqual(OTHER.var("RW_FILE"), "TOOLX_SANDBOX_RW_FILE")

    def test_real_profiles_name_their_own_tool(self):
        self.assertEqual(PROFILES["pi"].var("MODE"), "PI_SANDBOX_MODE")
        self.assertEqual(PROFILES["pier"].var("MODE"), "PIER_SANDBOX_MODE")


class NormalizeModeTest(unittest.TestCase):
    def test_spellings(self):
        for raw, want in [
            ("ro", "ro"), ("read-only", "ro"), ("READONLY", "ro"),
            ("fa", "fa"), ("full-access", "fa"), ("none", "fa"),
            ("ww", "ww"), ("", "ww"), ("bogus", "ww"), (None, "ww"),
        ]:
            self.assertEqual(sandbox.normalize_mode(raw), want, raw)


class IsRootTest(unittest.TestCase):
    def test_root_detected(self):
        self.assertTrue(sandbox.is_root(ROOT))

    def test_subdir_not_root(self):
        self.assertFalse(sandbox.is_root(os.path.join(HOME, "repos")))


class SubcommandTest(unittest.TestCase):
    def test_each_profile_knows_its_own_subcommands(self):
        for name, profile in PROFILES.items():
            for sub in profile.subcommands:
                with self.subTest(name, sub=sub):
                    self.assertTrue(sandbox.is_subcommand(profile, [sub]))

    def test_flags_and_empty_are_not_subcommands(self):
        for name, profile in PROFILES.items():
            with self.subTest(name):
                self.assertFalse(sandbox.is_subcommand(profile, []))
                self.assertFalse(sandbox.is_subcommand(profile, ["--model", "update"]))

    def test_another_tools_subcommand_is_not_mine(self):
        self.assertFalse(sandbox.is_subcommand(PROFILES["pier"], ["install"]))
        self.assertFalse(sandbox.is_subcommand(OTHER, ["update"]))


class PlanWritableTest(unittest.TestCase):
    def exists_all(self, *_):
        return True

    def each(self, fn):
        for name, profile in PROFILES.items():
            with self.subTest(name):
                fn(profile)

    def test_workspace_writable_in_ww(self):
        def check(profile):
            ws = os.path.join(HOME, "repos", "proj")
            got = sandbox.plan_writable(profile, ws, "ww", home=HOME,
                                        exists=self.exists_all, env={})
            self.assertIn(norm(ws), got)
            self.assertIn(norm(os.path.join(HOME, ".pi")), got)
            self.assertIn(norm(os.path.join(ROOT, "tmp")), got)

        self.each(check)

    def test_workspace_not_writable_in_ro(self):
        def check(profile):
            ws = os.path.join(HOME, "repos", "proj")
            got = sandbox.plan_writable(profile, ws, "ro", home=HOME,
                                        exists=self.exists_all, env={})
            self.assertNotIn(norm(ws), got)
            self.assertIn(norm(os.path.join(HOME, ".pi")), got)

        self.each(check)

    def test_home_itself_never_writable(self):
        def check(profile):
            got = sandbox.plan_writable(profile, os.path.join(HOME, "repos", "proj"),
                                        "ww", home=HOME, exists=self.exists_all, env={})
            self.assertNotIn(norm(HOME), got)

        self.each(check)

    def test_root_refused(self):
        def check(profile):
            got = sandbox.plan_writable(profile, ROOT, "ww", extra_rw=[ROOT],
                                        home=HOME, exists=self.exists_all, env={})
            self.assertNotIn(norm(ROOT), got)

        self.each(check)

    def test_nested_duplicate_dropped(self):
        def check(profile):
            repos = os.path.join(HOME, "repos")
            ws = os.path.join(repos, "proj")
            got = sandbox.plan_writable(profile, ws, "ww", extra_rw=[repos],
                                        home=HOME, exists=self.exists_all, env={})
            self.assertIn(norm(repos), got)
            self.assertNotIn(norm(ws), got)

        self.each(check)

    def test_sibling_prefix_kept(self):
        def check(profile):
            ws = os.path.join(HOME, "ws")
            sibling = os.path.join(HOME, "ws2")
            got = sandbox.plan_writable(profile, ws, "ww", extra_rw=[sibling],
                                        home=HOME, exists=self.exists_all, env={})
            self.assertIn(norm(ws), got)
            self.assertIn(norm(sibling), got)

        self.each(check)

    def test_missing_paths_filtered(self):
        def check(profile):
            ws = os.path.join(HOME, "repos", "proj")
            present = {absp(os.path.join(HOME, ".pi")), absp(os.path.join(ROOT, "tmp")), absp(ws)}
            got = sandbox.plan_writable(profile, ws, "ww", home=HOME,
                                        exists=lambda p: p in present, env={})
            self.assertEqual(sorted(got), sorted(norm(p) for p in present))

        self.each(check)

    def test_xdg_dirs_included(self):
        def check(profile):
            cache = os.path.join(ROOT, "x", "cache")
            data = os.path.join(ROOT, "x", "data")
            got = sandbox.plan_writable(profile, os.path.join(HOME, "ws"), "ro",
                                        home=HOME, exists=self.exists_all,
                                        env={"XDG_CACHE_HOME": cache, "XDG_DATA_HOME": data})
            self.assertIn(norm(cache), got)
            self.assertIn(norm(data), got)

        self.each(check)

    def test_runtime_dir_is_not_writable(self):
        def check(profile):
            runtime = os.path.join(ROOT, "run", "user", "1000")
            got = sandbox.plan_writable(profile, os.path.join(HOME, "ws"), "ro",
                                        home=HOME, exists=self.exists_all,
                                        env={"XDG_RUNTIME_DIR": runtime})
            self.assertNotIn(norm(runtime), got)

        self.each(check)

    def test_agent_state_dirs_from_the_profile(self):
        def check(profile):
            env = {var: os.path.join(ROOT, "x", var) for var in profile.agent_dir_vars}
            got = sandbox.plan_writable(profile, os.path.join(HOME, "ws"), "ro",
                                        home=HOME, exists=self.exists_all, env=env)
            for value in env.values():
                self.assertIn(norm(value), got)

        self.each(check)

    def test_unrelated_agent_state_var_ignored(self):
        got = sandbox.plan_writable(OTHER, os.path.join(HOME, "ws"), "ro", home=HOME,
                                    exists=self.exists_all, env={"PI_CODING_AGENT_DIR": "/x/pi"})
        self.assertNotIn(norm("/x/pi"), got)

    def test_known_hosts_writable(self):
        def check(profile):
            got = sandbox.plan_writable(profile, os.path.join(HOME, "ws"), "ww",
                                        home=HOME, exists=self.exists_all, env={})
            self.assertIn(norm(os.path.join(HOME, ".ssh", "known_hosts")), got)

        self.each(check)

    def test_aws_caches_writable_but_credentials_read_only(self):
        def check(profile):
            got = sandbox.plan_writable(profile, os.path.join(HOME, "ws"), "ww",
                                        home=HOME, exists=self.exists_all, env={})
            self.assertIn(norm(os.path.join(HOME, ".aws", "cli", "cache")), got)
            self.assertIn(norm(os.path.join(HOME, ".aws", "sso", "cache")), got)
            self.assertNotIn(norm(os.path.join(HOME, ".aws")), got)
            self.assertNotIn(norm(os.path.join(HOME, ".aws", "config")), got)
            self.assertNotIn(norm(os.path.join(HOME, ".aws", "credentials")), got)

        self.each(check)


class ConfigRwPathsTest(unittest.TestCase):
    def test_reads_paths_and_comments(self):
        for name, profile in PROFILES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "rw")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("# extra writable paths\n\n  ~/extra  \n/x/y # trailing\n")
                got = sandbox.config_rw_paths(profile, env={profile.var("RW_FILE"): path})
            self.assertEqual(got, [os.path.expanduser("~/extra"), "/x/y"])

    def test_missing_file_is_empty(self):
        for name, profile in PROFILES.items():
            with self.subTest(name):
                self.assertEqual(
                    sandbox.config_rw_paths(profile, env={profile.var("RW_FILE"): "/no/such/file"}), [])

    def test_default_file_is_named_after_the_tool(self):
        for name, profile in PROFILES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                directory = os.path.join(tmp, ".config", f"{profile.tool}_sandbox")
                os.makedirs(directory)
                with open(os.path.join(directory, "rw"), "w", encoding="utf-8") as handle:
                    handle.write("/from/default/file\n")
                got = sandbox.config_rw_paths(profile, env={}, home=tmp)
            self.assertEqual(got, ["/from/default/file"])


class RemoteEnvTest(unittest.TestCase):
    """Env vars for host services the tool can only reach as a client.

    bwrap sets no_new_privs and maps only the caller's uid, so rootless podman
    cannot create its own user namespace inside the sandbox. It can only talk
    to the user's service, which is found through the socket that service owns.
    """

    runtime = os.path.join(ROOT, "run", "user", "1000")

    def socket(self, profile):
        _var, rel = profile.remote_sockets[0]
        return os.path.join(self.runtime, rel)

    def each(self, fn):
        for name, profile in PROFILES.items():
            with self.subTest(name):
                fn(profile)

    def test_socket_env_set_when_the_socket_exists(self):
        def check(profile):
            var, _rel = profile.remote_sockets[0]
            got = sandbox.remote_env(profile, env={"XDG_RUNTIME_DIR": self.runtime},
                                     exists=lambda p: p == self.socket(profile))
            self.assertEqual(got, {var: "unix://" + self.socket(profile)})

        self.each(check)

    def test_nothing_when_the_socket_is_missing(self):
        def check(profile):
            got = sandbox.remote_env(profile, env={"XDG_RUNTIME_DIR": self.runtime},
                                     exists=lambda p: False)
            self.assertEqual(got, {})

        self.each(check)

    def test_nothing_without_a_runtime_dir(self):
        def check(profile):
            self.assertEqual(sandbox.remote_env(profile, env={}, exists=lambda p: True), {})

        self.each(check)


class RuntimeMountsTest(unittest.TestCase):
    """The runtime dir becomes a private tmpfs holding only the sockets we allow.

    Everything else in it is a way to act on the host: the session bus and the
    systemd user manager run commands as the user outside the sandbox, and the
    remaining sockets drive pipewire, dconf, kwallet, at-spi, and the yazi and
    mpv IPC endpoints.
    """

    runtime = os.path.join(ROOT, "run", "user", "1000")

    def sock(self, profile):
        _var, rel = profile.remote_sockets[0]
        return os.path.join(self.runtime, rel)

    def each(self, fn):
        for name, profile in PROFILES.items():
            with self.subTest(name):
                fn(profile)

    def test_tmpfs_then_the_profile_socket(self):
        def check(profile):
            socket = self.sock(profile)
            got = sandbox.plan_runtime_mounts(profile, env={"XDG_RUNTIME_DIR": self.runtime},
                                              exists=lambda p: p == socket,
                                              isdir=lambda p: True)
            self.assertEqual(got, ["--tmpfs", self.runtime,
                                   "--dir", os.path.dirname(socket),
                                   "--ro-bind-try", socket, socket])

        self.each(check)

    def test_nothing_without_a_runtime_dir(self):
        def check(profile):
            self.assertEqual(
                sandbox.plan_runtime_mounts(profile, env={}, exists=lambda p: True,
                                            isdir=lambda p: True),
                [])

        self.each(check)

    def test_nothing_when_the_runtime_dir_is_missing(self):
        def check(profile):
            self.assertEqual(
                sandbox.plan_runtime_mounts(profile, env={"XDG_RUNTIME_DIR": self.runtime},
                                            exists=lambda p: True, isdir=lambda p: False),
                [])

        self.each(check)

    def test_missing_sockets_are_not_bound(self):
        def check(profile):
            got = sandbox.plan_runtime_mounts(profile, env={"XDG_RUNTIME_DIR": self.runtime},
                                              exists=lambda p: False, isdir=lambda p: True)
            self.assertEqual(got, ["--tmpfs", self.runtime])

        self.each(check)

    def test_ssh_agent_socket_inside_the_runtime_dir_is_kept(self):
        def check(profile):
            agent = os.path.join(self.runtime, "ssh-agent.socket")
            env = {"XDG_RUNTIME_DIR": self.runtime, "SSH_AUTH_SOCK": agent}
            got = sandbox.plan_runtime_mounts(profile, env=env, exists=lambda p: p == agent,
                                              isdir=lambda p: True)
            self.assertEqual(got, ["--tmpfs", self.runtime,
                                   "--ro-bind-try", agent, agent])

        self.each(check)

    def test_ssh_agent_socket_nested_in_the_runtime_dir_is_kept(self):
        def check(profile):
            agent = os.path.join(self.runtime, "keyring", "ssh")
            env = {"XDG_RUNTIME_DIR": self.runtime, "SSH_AUTH_SOCK": agent}
            got = sandbox.plan_runtime_mounts(profile, env=env, exists=lambda p: p == agent,
                                              isdir=lambda p: True)
            self.assertEqual(got, ["--tmpfs", self.runtime,
                                   "--dir", os.path.join(self.runtime, "keyring"),
                                   "--ro-bind-try", agent, agent])

        self.each(check)

    def test_ssh_agent_socket_outside_the_runtime_dir_is_left_alone(self):
        def check(profile):
            agent = os.path.join(ROOT, "tmp", "agent.sock")
            env = {"XDG_RUNTIME_DIR": self.runtime, "SSH_AUTH_SOCK": agent}
            got = sandbox.plan_runtime_mounts(profile, env=env, exists=lambda p: p == agent,
                                              isdir=lambda p: True)
            self.assertEqual(got, ["--tmpfs", self.runtime])

        self.each(check)


class HostMasksTest(unittest.TestCase):
    """Host IPC endpoints outside the runtime dir that drive the session.

    Each one can run or steer something outside the sandbox: the system bus
    (logind power actions and every polkit-mediated call), X11, ICE session
    management, and the XIM input method (keystroke capture and input
    injection), and tmux (send-keys runs commands in the user's panes).
    """

    def test_covers_the_session_and_system_control_sockets(self):
        got = sandbox.plan_host_masks(exists=lambda p: True, isdir=lambda p: True)
        for path in ("/run/dbus/system_bus_socket", "/tmp/.X11-unix", "/tmp/.ICE-unix",
                     "/tmp/.XIM-unix", f"/tmp/tmux-{sandbox.UID}",
                     "/run/systemd/journal"):
            with self.subTest(path):
                self.assertIn(path, got)

    def test_socket_files_become_dev_null(self):
        got = sandbox.plan_host_masks(exists=lambda p: True, isdir=lambda p: False)
        at = got.index("/run/dbus/system_bus_socket")
        self.assertEqual(got[at - 2:at + 1],
                         ["--bind-try", "/dev/null", "/run/dbus/system_bus_socket"])

    def test_socket_directories_are_emptied_with_a_tmpfs(self):
        got = sandbox.plan_host_masks(exists=lambda p: True,
                                      isdir=lambda p: p == "/tmp/.X11-unix")
        at = got.index("/tmp/.X11-unix")
        self.assertEqual(got[at - 1:at + 1], ["--tmpfs", "/tmp/.X11-unix"])

    def test_missing_paths_are_skipped(self):
        self.assertEqual(
            sandbox.plan_host_masks(exists=lambda p: False, isdir=lambda p: False), [])


class BuildArgvTest(unittest.TestCase):
    def test_shape(self):
        argv = sandbox.build_bwrap_argv(
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
        # The tool and its args come after the "--" terminator, marker before it.
        sep = argv.index("--")
        self.assertEqual(argv[sep + 1:], ["/usr/bin/pi", "-c", "hi"])
        self.assertEqual(argv[argv.index("PI_BWRAP") - 1], "--setenv")

    def test_ssh_config_dir_masked(self):
        argv = sandbox.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                       "/home/u/proj", [], "/etc/ssh/ssh_config.d")
        at = argv.index("--tmpfs")
        self.assertEqual(argv[at:at + 2], ["--tmpfs", "/etc/ssh/ssh_config.d"])

    def test_no_ssh_tmpfs_when_unset(self):
        argv = sandbox.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                       "/home/u/proj", [])
        self.assertNotIn("--tmpfs", argv)

    def test_remote_env_passed_to_the_tool(self):
        argv = sandbox.build_bwrap_argv(
            "/usr/bin/bwrap", "/usr/bin/pi", [], "/home/u/proj", [],
            env_extra={"CONTAINER_HOST": "unix:///run/user/1000/podman/podman.sock"},
        )
        at = argv.index("CONTAINER_HOST")
        self.assertEqual(argv[at - 1], "--setenv")
        self.assertEqual(argv[at + 1], "unix:///run/user/1000/podman/podman.sock")
        self.assertLess(at, argv.index("--"))

    def test_no_remote_env_by_default(self):
        argv = sandbox.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                       "/home/u/proj", [])
        self.assertNotIn("CONTAINER_HOST", argv)

    def test_runtime_mounts_placed_before_the_tool(self):
        argv = sandbox.build_bwrap_argv(
            "/usr/bin/bwrap", "/usr/bin/pi", [], "/home/u/proj", [],
            runtime_mounts=["--tmpfs", "/run/user/1000"],
        )
        at = argv.index("--tmpfs")
        self.assertEqual(argv[at:at + 2], ["--tmpfs", "/run/user/1000"])
        self.assertLess(at, argv.index("--"))

    def test_no_runtime_mounts_by_default(self):
        argv = sandbox.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                       "/home/u/proj", [])
        self.assertNotIn("--tmpfs", argv)

    def test_masks_follow_the_writable_binds(self):
        argv = sandbox.build_bwrap_argv(
            "/usr/bin/bwrap", "/usr/bin/pi", [], "/home/u/proj", ["/tmp", "/home/u/proj"],
            host_masks=["--tmpfs", "/tmp/.X11-unix"],
        )
        last_bind = max(i for i, arg in enumerate(argv) if arg == "--bind-try")
        self.assertGreater(argv.index("/tmp/.X11-unix"), last_bind)
        self.assertLess(argv.index("/tmp/.X11-unix"), argv.index("--"))

    def test_isolated_pid_and_ipc_namespaces(self):
        argv = sandbox.build_bwrap_argv("/usr/bin/bwrap", "/usr/bin/pi", [],
                                       "/home/u/proj", [])
        self.assertEqual(argv.count("--unshare-pid"), 1)
        self.assertEqual(argv.count("--unshare-ipc"), 1)
        self.assertIn("--proc", argv)


class WarnTest(unittest.TestCase):
    def test_prefixed_with_the_tool(self):
        for name, profile in PROFILES.items():
            with self.subTest(name), contextlib.redirect_stderr(io.StringIO()) as err:
                sandbox.warn(profile, "something happened")
            self.assertEqual(err.getvalue(), f"{profile.tool}_sandbox: something happened\n")

    def test_quiet_suppresses(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            sandbox.warn(OTHER, "something happened", quiet=True)
        self.assertEqual(err.getvalue(), "")


class MainTest(unittest.TestCase):
    def setUp(self):
        self.ws = os.getcwd()
        self.calls = []

        def execvp(file, args):
            self.calls.append((file, list(args)))

        self.execvp = execvp

    def run_main(self, profile, argv=None, env=None, **over):
        kwargs = dict(
            env=env if env is not None else {},
            execvp=self.execvp,
            which=lambda name: {profile.tool: f"/usr/bin/{profile.tool}",
                                "bwrap": "/usr/bin/bwrap"}.get(name),
            exists=lambda p: True,
            isdir=lambda p: True,
            probe=lambda bwrap: True,
            is_linux=True,
        )
        kwargs.update(over)
        return sandbox.main(profile, argv if argv is not None else [], **kwargs)

    def base_env(self, profile, **extra):
        env = {profile.var("WORKSPACE"): self.ws}
        env.update(extra)
        return env

    def each(self, fn):
        for name, profile in PROFILES.items():
            self.calls.clear()
            with self.subTest(name):
                fn(profile)

    def test_sandbox_execs_bwrap(self):
        def check(profile):
            rc = self.run_main(profile, env=self.base_env(profile))
            self.assertEqual(rc, 127)  # execvp double returns
            self.assertEqual(len(self.calls), 1)
            file, args = self.calls[0]
            self.assertEqual(file, "/usr/bin/bwrap")
            self.assertIn("--ro-bind", args)
            self.assertIn(absp(self.ws), args)

        self.each(check)

    def test_fa_runs_the_tool_directly(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile, **{profile.var("MODE"): "fa"}))
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_disable_runs_the_tool_directly(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile, **{profile.var("DISABLE"): "1"}))
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_nested_marker_runs_the_tool_directly(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile, PI_BWRAP="1"))
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_non_linux_falls_back(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile), is_linux=False)
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_missing_bwrap_falls_back(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile),
                          which=lambda name: f"/usr/bin/{profile.tool}" if name == profile.tool else None)
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_probe_failure_falls_back(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile), probe=lambda bwrap: False)
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_missing_tool_is_127(self):
        def check(profile):
            rc = self.run_main(profile, env=self.base_env(profile), which=lambda name: None)
            self.assertEqual(rc, 127)
            self.assertEqual(self.calls, [])

        self.each(check)

    def test_explicit_tool_path_is_used(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile, **{profile.var(profile.tool.upper()): "/opt/tool"}),
                          argv=["--version"])
            self.assertEqual(self.calls[0][0], "/usr/bin/bwrap")
            self.assertEqual(self.calls[0][1][-2:], ["/opt/tool", "--version"])

        self.each(check)

    def test_root_workspace_falls_back(self):
        def check(profile):
            self.run_main(profile, env={profile.var("WORKSPACE"): ROOT})
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")

        self.each(check)

    def test_missing_workspace_is_2(self):
        def check(profile):
            env = {profile.var("WORKSPACE"): os.path.join(ROOT, "does", "not", "exist")}
            rc = self.run_main(profile, env=env, exists=lambda p: False, isdir=lambda p: False)
            self.assertEqual(rc, 2)
            self.assertEqual(self.calls, [])

        self.each(check)

    def test_dry_run_prints_command(self):
        def check(profile):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = self.run_main(profile, env=self.base_env(profile, **{profile.var("DRY_RUN"): "1"}))
            self.assertEqual(rc, 0)
            self.assertEqual(self.calls, [])
            self.assertIn("/usr/bin/bwrap", buf.getvalue())
            self.assertIn("--ro-bind / /", buf.getvalue())

        self.each(check)

    def test_extra_rw_paths_bound(self):
        def check(profile):
            one = os.path.join(ROOT, "extra", "one")
            two = os.path.join(ROOT, "extra", "two")
            self.run_main(profile, env=self.base_env(profile, **{profile.var("RW"): one + os.pathsep + two}))
            _, args = self.calls[0]
            self.assertIn(norm(one), args)
            self.assertIn(norm(two), args)

        self.each(check)

    def test_config_file_paths_bound(self):
        def check(profile):
            extra = os.path.join(ROOT, "cfg", "extra")
            with tempfile.TemporaryDirectory() as tmp:
                rw = os.path.join(tmp, "rw")
                with open(rw, "w", encoding="utf-8") as handle:
                    handle.write(extra + "\n")
                self.run_main(profile, env=self.base_env(profile, **{profile.var("RW_FILE"): rw}))
            _, args = self.calls[0]
            self.assertIn(norm(extra), args)

        self.each(check)

    def test_ssh_config_dir_masked(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile))
            _, args = self.calls[0]
            at = args.index("--tmpfs")
            self.assertEqual(args[at:at + 2], ["--tmpfs", sandbox.SSH_CONFIG_DIR])

        self.each(check)

    def test_tool_args_passed_through(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile), argv=["-c", "hello world"])
            _, args = self.calls[0]
            self.assertEqual(args[args.index("--") + 1:], [f"/usr/bin/{profile.tool}", "-c", "hello world"])

        self.each(check)

    def test_subcommand_runs_the_tool_directly(self):
        def check(profile):
            sub = profile.subcommands[0]
            self.run_main(profile, env=self.base_env(profile), argv=[sub, "extra"])
            self.assertEqual(self.calls[0][0], f"/usr/bin/{profile.tool}")
            self.assertEqual(self.calls[0][1], [f"/usr/bin/{profile.tool}", sub, "extra"])

        self.each(check)

    def test_container_socket_env_is_forwarded(self):
        def check(profile):
            var, rel = profile.remote_sockets[0]
            runtime = os.path.join(ROOT, "run", "user", "1000")
            self.run_main(profile, env=self.base_env(profile, XDG_RUNTIME_DIR=runtime))
            _, args = self.calls[0]
            at = args.index(var)
            self.assertEqual(args[at - 1], "--setenv")
            self.assertEqual(args[at + 1], "unix://" + os.path.join(runtime, rel))

        self.each(check)

    def test_no_container_socket_env_without_the_socket(self):
        def check(profile):
            var, _rel = profile.remote_sockets[0]
            runtime = os.path.join(ROOT, "run", "user", "1000")
            self.run_main(profile, env=self.base_env(profile, XDG_RUNTIME_DIR=runtime),
                          exists=lambda p: False)
            _, args = self.calls[0]
            self.assertNotIn(var, args)

        self.each(check)

    def test_runtime_dir_masked_with_only_the_needed_sockets(self):
        def check(profile):
            runtime = os.path.join(ROOT, "run", "user", "1000")
            _var, rel = profile.remote_sockets[0]
            socket = os.path.join(runtime, rel)
            env = self.base_env(profile, XDG_RUNTIME_DIR=runtime)
            self.run_main(profile, env=env)
            _, args = self.calls[0]
            at = args.index(runtime)
            self.assertEqual(args[at - 1], "--tmpfs")
            self.assertEqual(args[args.index(socket) - 1], "--ro-bind-try")
            writable = [args[i + 1] for i, arg in enumerate(args) if arg == "--bind-try"]
            self.assertNotIn(runtime, writable)

        self.each(check)

    def test_host_control_sockets_are_masked_after_the_writable_binds(self):
        def check(profile):
            self.run_main(profile, env=self.base_env(profile))
            _, args = self.calls[0]
            self.assertIn("/run/dbus/system_bus_socket", args)
            self.assertIn("/tmp/.X11-unix", args)
            binds = [i for i, arg in enumerate(args)
                     if arg == "--bind-try" and args[i + 1] != "/dev/null"]
            self.assertGreater(args.index("/tmp/.X11-unix"), max(binds))

        self.each(check)

    def test_quiet_var_suppresses_the_fallback_warning(self):
        def check(profile):
            env = self.base_env(profile, **{profile.var("QUIET"): "1"})
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.run_main(profile, env=env, is_linux=False)
            self.assertEqual(err.getvalue(), "")

        self.each(check)


if __name__ == "__main__":
    unittest.main()
