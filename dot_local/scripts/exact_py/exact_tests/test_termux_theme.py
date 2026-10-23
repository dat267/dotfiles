import pathlib
import random
import tempfile
import unittest
from unittest import mock

import _loader

mod = _loader.load("termux_theme")


class TestParseNight(unittest.TestCase):
    r"""Android reports the flag in three shapes depending on the channel:
    `cmd uimode night` prints "Night mode: yes", `settings get` prints 1/0, and
    some builds print a bare yes/no. A probe that errors prints permission
    text, which must not be mistaken for a mode."""

    def test_cmd_uimode_output(self):
        self.assertEqual(mod.parse_night("\nNight mode: yes\n"), "dark")
        self.assertEqual(mod.parse_night("Night mode: no"), "light")

    def test_settings_output(self):
        self.assertEqual(mod.parse_night("1\n"), "dark")
        self.assertEqual(mod.parse_night("0\n"), "light")

    def test_bare_words(self):
        self.assertEqual(mod.parse_night("yes"), "dark")
        self.assertEqual(mod.parse_night("NO"), "light")

    def test_permission_denial_is_not_a_mode(self):
        self.assertIsNone(
            mod.parse_night(
                "java.lang.SecurityException: Access denied, requires: "
                "android.permission.MODIFY_DAY_NIGHT_MODE"
            )
        )

    def test_empty_is_not_a_mode(self):
        self.assertIsNone(mod.parse_night(""))


class TestDetectMode(unittest.TestCase):
    """Probes run in order and a denied or missing channel must fall through to
    the next one, because which channel is usable differs per device: root or
    shell can use `cmd`, Shizuku can use `rish`, otherwise nothing works."""

    def test_falls_through_denied_probe(self):
        def run(argv, **kwargs):
            if argv[0] == "cmd":
                raise mod.subprocess.CalledProcessError(1, argv)
            return mock.Mock(stdout="Night mode: no\n")

        self.assertEqual(mod.detect_mode(run=run, which=lambda c: f"/bin/{c}"), "light")

    def test_skips_missing_binaries(self):
        seen = []

        def run(argv, **kwargs):
            seen.append(argv[0])
            return mock.Mock(stdout="1\n")

        self.assertEqual(mod.detect_mode(run=run, which=lambda c: None), None)
        self.assertEqual(seen, [])

    def test_returns_none_when_no_channel_answers(self):
        def run(argv, **kwargs):
            return mock.Mock(stdout="Exception occurred\n")

        self.assertIsNone(mod.detect_mode(run=run, which=lambda c: f"/bin/{c}"))

    def test_timeout_falls_through(self):
        def run(argv, **kwargs):
            if argv[0] == "cmd":
                raise mod.subprocess.TimeoutExpired(argv, 5)
            return mock.Mock(stdout="Night mode: yes\n")

        self.assertEqual(mod.detect_mode(run=run, which=lambda c: f"/bin/{c}"), "dark")


class TestPool(unittest.TestCase):
    """The pool is `themes/<mode>/*.properties`; anything else in the directory
    (README, backup files) must be ignored so a stray file cannot be applied."""

    def test_lists_only_properties_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "b.properties").write_text("b")
            (p / "a.properties").write_text("a")
            (p / "notes.md").write_text("x")
            (p / "a.properties.bak").write_text("y")
            self.assertEqual(
                [f.name for f in mod.pool_files(p)],
                ["a.properties", "b.properties"],
            )

    def test_missing_directory_is_empty(self):
        self.assertEqual(mod.pool_files(pathlib.Path("/nonexistent/dark")), [])

    def test_choose_is_deterministic_for_a_seed(self):
        files = [pathlib.Path(f"/t/{n}.properties") for n in "abcd"]
        self.assertEqual(
            mod.choose(files, random.Random(7)), mod.choose(files, random.Random(7))
        )

    def test_every_theme_in_the_pool_can_be_picked(self):
        files = [pathlib.Path(f"/t/{n}.properties") for n in "abcd"]
        seen = {mod.choose(files, random.Random(s)).name for s in range(200)}
        self.assertEqual(seen, {f.name for f in files})


class TestResolveMode(unittest.TestCase):
    r"""Precedence: an explicit --mode beats detection (so a wrong probe can be
    overridden), detection beats the sticky state, and with no signal at all the
    session still gets a theme rather than an error."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = pathlib.Path(self.tmp.name) / "mode"

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_beats_detection(self):
        self.assertEqual(
            mod.resolve_mode("light", self.state, detect=lambda: "dark"), "light"
        )

    def test_detection_beats_state(self):
        mod.write_state(self.state, "light")
        self.assertEqual(
            mod.resolve_mode("auto", self.state, detect=lambda: "dark"), "dark"
        )

    def test_state_is_the_fallback(self):
        mod.write_state(self.state, "light")
        self.assertEqual(
            mod.resolve_mode("auto", self.state, detect=lambda: None), "light"
        )

    def test_default_without_any_signal(self):
        self.assertEqual(
            mod.resolve_mode("auto", self.state, detect=lambda: None), "dark"
        )

    def test_corrupt_state_is_ignored(self):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text("banana\n")
        self.assertEqual(
            mod.resolve_mode("auto", self.state, detect=lambda: None), "dark"
        )


class TestMain(unittest.TestCase):
    """Dry run must not touch the live colors file, --set only records the mode
    (an automation app calls it), and a missing pool reports rather than
    silently leaving the terminal themeless."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.dark = self.root / "themes" / "dark"
        self.dark.mkdir(parents=True)
        (self.dark / "one.properties").write_text("background=#111111\n")
        (self.dark / "two.properties").write_text("background=#222222\n")
        self.dest = self.root / "colors.properties"
        self.state = self.root / "state"
        self.argv = [
            "--theme-dir", str(self.root / "themes"),
            "--dest", str(self.dest),
            "--state", str(self.state),
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_writes_nothing(self):
        with mock.patch.object(mod, "detect_mode", return_value="dark"), mock.patch.object(
            mod.shutil, "which", return_value=None
        ):
            self.assertEqual(mod.main(self.argv + ["--dry-run"]), 0)
        self.assertFalse(self.dest.exists())

    def test_applies_the_chosen_theme(self):
        with mock.patch.object(mod, "detect_mode", return_value="dark"), mock.patch.object(
            mod.shutil, "which", return_value=None
        ), mock.patch.object(mod, "choose", return_value=self.dark / "one.properties"):
            self.assertEqual(mod.main(self.argv), 0)
        self.assertEqual(self.dest.read_text(), "background=#111111\n")

    def test_reloads_the_terminal_when_available(self):
        with mock.patch.object(mod, "detect_mode", return_value="dark"), mock.patch.object(
            mod.shutil, "which", return_value="/bin/termux-reload-settings"
        ), mock.patch.object(mod.subprocess, "run") as run, mock.patch.object(
            mod, "choose", return_value=self.dark / "one.properties"
        ):
            self.assertEqual(mod.main(self.argv), 0)
        self.assertEqual(run.call_args[0][0], ["termux-reload-settings"])

    def test_no_reload_flag(self):
        with mock.patch.object(mod, "detect_mode", return_value="dark"), mock.patch.object(
            mod.shutil, "which", return_value="/bin/termux-reload-settings"
        ), mock.patch.object(mod.subprocess, "run") as run, mock.patch.object(
            mod, "choose", return_value=self.dark / "one.properties"
        ):
            self.assertEqual(mod.main(self.argv + ["--no-reload"]), 0)
        run.assert_not_called()

    def test_set_records_the_mode_and_changes_no_theme(self):
        with mock.patch.object(mod, "detect_mode", return_value="dark"), mock.patch.object(
            mod.shutil, "which", return_value=None
        ):
            self.assertEqual(mod.main(self.argv + ["--set", "light"]), 0)
        self.assertEqual(self.state.read_text().strip(), "light")
        self.assertFalse(self.dest.exists())

    def test_empty_pool_is_reported(self):
        with mock.patch.object(mod, "detect_mode", return_value="light"), mock.patch.object(
            mod.shutil, "which", return_value=None
        ):
            self.assertEqual(mod.main(self.argv), 1)
        self.assertFalse(self.dest.exists())


if __name__ == "__main__":
    unittest.main()
