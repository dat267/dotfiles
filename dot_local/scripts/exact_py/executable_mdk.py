#!/usr/bin/env python3
"""One-shot markdown search: rg lists the matching lines, fzf picks one, the
editor opens at the match. With no pattern every markdown line is a candidate.

Wired to the `mdk` alias in the shared profile; also runnable directly.
Requires ripgrep, fzf, and bat (bat only for the preview).
"""
import argparse
import os
import shutil
import subprocess
import sys

from _shared import log

GLOB = "*.md"
EDITORS = ("nvim", "vim", "hx", "helix", "nano")


def resolve_editor(env=None):
    """$EDITOR, then $VISUAL, then the first editor on PATH."""
    env = os.environ if env is None else env
    editor = env.get("EDITOR") or env.get("VISUAL")
    if editor:
        return editor
    for candidate in EDITORS:
        if shutil.which(candidate):
            return candidate
    return "nvim"


def opener(editor):
    """The fzf `become` command: helix wants file:line, vim-style +line file."""
    if os.path.basename(editor) in ("hx", "helix"):
        return f"{editor} {{1}}:{{2}}"
    return f"{editor} +{{2}} {{1}}"


def rg_args(pattern):
    return [
        "rg", "--line-number", "--no-heading", "--color=always", "--smart-case",
        "--glob", GLOB, pattern,
    ]


def fzf_args(editor):
    return [
        "fzf", "--ansi", "--delimiter", ":", "--nth", "3..",
        "--preview", "bat --style=numbers --color=always --highlight-line {2} {1}",
        "--preview-window", "right:60%:+{2}+3/3",
        "--bind", f"enter:become({opener(editor)})",
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Search markdown with ripgrep and open the match in $EDITOR.",
    )
    parser.add_argument("pattern", nargs="?", default="",
                        help="ripgrep pattern (default: every markdown line)")
    args = parser.parse_args()

    for tool in ("rg", "fzf"):
        if not shutil.which(tool):
            log(f"Error: {tool} is required.", "red")
            sys.exit(1)

    matches = subprocess.run(rg_args(args.pattern), stdout=subprocess.PIPE, text=True)
    result = subprocess.run(fzf_args(resolve_editor()), input=matches.stdout, text=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
