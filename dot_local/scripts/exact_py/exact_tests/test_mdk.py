"""mdk: one-shot markdown search. rg lists matches, fzf picks, editor opens."""

import unittest
from unittest import mock

import _loader

mdk = _loader.load("mdk")


class TestCommandConstruction(unittest.TestCase):
    def test_rg_args_search_markdown_for_the_pattern(self):
        args = mdk.rg_args("needle")
        self.assertEqual(args[0], "rg")
        self.assertIn("--glob", args)
        self.assertIn("*.md", args)
        self.assertEqual(args[-1], "needle")

    def test_rg_args_without_pattern_search_every_line(self):
        self.assertEqual(mdk.rg_args("")[-1], "")

    def test_opener_for_vim_style_editors(self):
        self.assertEqual(mdk.opener("nvim"), "nvim +{2} {1}")

    def test_opener_for_helix_uses_inline_line_numbers(self):
        self.assertEqual(mdk.opener("hx"), "hx {1}:{2}")
        self.assertEqual(mdk.opener("/usr/bin/helix"), "/usr/bin/helix {1}:{2}")

    def test_fzf_args_bind_the_opener_and_preview_the_match(self):
        args = mdk.fzf_args("nvim")
        self.assertEqual(args[0], "fzf")
        self.assertIn("enter:become(nvim +{2} {1})", args)
        self.assertIn("--highlight-line {2} {1}", " ".join(args))


class TestResolveEditor(unittest.TestCase):
    def test_editor_env_wins(self):
        self.assertEqual(mdk.resolve_editor({"EDITOR": "hx"}), "hx")

    def test_visual_is_the_fallback(self):
        self.assertEqual(mdk.resolve_editor({"VISUAL": "vim"}), "vim")

    def test_probes_when_neither_is_set(self):
        with mock.patch.object(mdk.shutil, "which",
                               side_effect=lambda name: "/x/hx" if name == "hx" else None):
            self.assertEqual(mdk.resolve_editor({}), "hx")

    def test_last_resort_is_nvim(self):
        with mock.patch.object(mdk.shutil, "which", return_value=None):
            self.assertEqual(mdk.resolve_editor({}), "nvim")


class TestMain(unittest.TestCase):
    def call_main(self, argv, run, which=None, editor="nvim"):
        with mock.patch.object(mdk.sys, "argv", ["mdk", *argv]), \
                mock.patch.object(mdk.shutil, "which", which or (lambda name: "/usr/bin/" + name)), \
                mock.patch.object(mdk.subprocess, "run", run), \
                mock.patch.object(mdk, "resolve_editor", return_value=editor):
            mdk.main()

    def test_pipes_rg_output_into_fzf_and_propagates_its_status(self):
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            if args[0] == "rg":
                return mock.Mock(stdout="notes/x.md:12:needle here\n")
            return mock.Mock(returncode=3)

        with self.assertRaises(SystemExit) as exit:
            self.call_main(["needle"], run)
        self.assertEqual(exit.exception.code, 3)
        self.assertEqual([args[0] for args, _ in calls], ["rg", "fzf"])
        self.assertEqual(calls[0][0], mdk.rg_args("needle"))
        self.assertEqual(calls[1][0], mdk.fzf_args("nvim"))
        self.assertEqual(calls[1][1]["input"], "notes/x.md:12:needle here\n")

    def test_missing_tool_exits_before_running_anything(self):
        run = mock.Mock()
        with mock.patch.object(mdk.sys, "argv", ["mdk", "needle"]), \
                mock.patch.object(mdk.shutil, "which", return_value=None), \
                mock.patch.object(mdk.subprocess, "run", run), \
                mock.patch.object(mdk, "resolve_editor", return_value="nvim"):
            with self.assertRaises(SystemExit) as exit:
                mdk.main()
        self.assertEqual(exit.exception.code, 1)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
