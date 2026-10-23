#!/usr/bin/env python3
"""Apply a random terminal theme from a dark or light pool, following the
device's day/night mode where (and only where) it can be read.

Termux has no auto mode: colors.properties is static, the app exposes no
theme setting, and Android does not let an unprivileged app read
Settings.Secure.ui_night_mode. So detection is best-effort over whatever
channel this device happens to grant (`cmd uimode` under shell/root,
`rish` under Shizuku, or an adb connection), and it falls back to a sticky
mode file that the user or an automation app can write:

    termux_theme.py --set dark

Layout: themes/<dark|light>/*.properties next to the generated
~/.termux/colors.properties.
"""

import argparse
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys

RELOAD_CMD = "termux-reload-settings"
DEFAULT_THEME_DIR = "~/.termux/themes"
DEFAULT_DEST = "~/.termux/colors.properties"
DEFAULT_STATE = "~/.cache/termux-theme/mode"
MODES = ("dark", "light")
PROBE_TIMEOUT = 5

# Tried in order; the first channel that answers wins. `cmd` works under a
# shell uid (root or Shizuku-disconnected adb), `rish` is the Shizuku shell,
# `settings` is the plain binary, and adb covers a tethered device.
PROBE_COMMANDS = [
    ["cmd", "uimode", "night"],
    ["rish", "-c", "cmd uimode night"],
    ["settings", "get", "secure", "ui_night_mode"],
    ["adb", "shell", "cmd uimode night"],
]


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def parse_night(text: str) -> str | None:
    """Map a probe's stdout to "dark"/"light", or None when it is not an answer.

    Permission denials mention the permission name and would otherwise look
    like success, so only exact words and the "Night mode: yes|no" form count.
    """
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in ("1", "yes", "true", "dark"):
        return "dark"
    if t in ("0", "no", "false", "light"):
        return "light"
    m = re.search(r"night mode:\s*(yes|no)", t)
    if m:
        return "dark" if m.group(1) == "yes" else "light"
    return None


def detect_mode(run=None, which=None) -> str | None:
    """Ask Android for its day/night mode through the first channel that works."""
    run = run or subprocess.run
    which = which or shutil.which
    for argv in PROBE_COMMANDS:
        if not which(argv[0]):
            continue
        try:
            res = run(argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            continue
        mode = parse_night(getattr(res, "stdout", "") or "")
        if mode:
            return mode
    return None


def read_state(path: pathlib.Path) -> str | None:
    try:
        mode = path.read_text().strip().lower()
    except OSError:
        return None
    return mode if mode in MODES else None


def write_state(path: pathlib.Path, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mode + "\n")


def resolve_mode(explicit: str, state_path: pathlib.Path, detect=None) -> str:
    """Explicit flag beats detection, detection beats the sticky file, and the
    last resort is dark so a session always gets a theme."""
    if explicit in MODES:
        return explicit
    if detect is None:
        detect = detect_mode
    return detect() or read_state(state_path) or "dark"


def pool_files(theme_dir: pathlib.Path) -> list[pathlib.Path]:
    if not theme_dir.is_dir():
        return []
    return sorted(p for p in theme_dir.glob("*.properties") if p.is_file())


def choose(files: list[pathlib.Path], rng: random.Random) -> pathlib.Path:
    return rng.choice(files)


def apply_theme(theme: pathlib.Path, dest: pathlib.Path, reload: bool = True) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(theme, dest)
    if reload and shutil.which(RELOAD_CMD):
        subprocess.run([RELOAD_CMD], check=False, capture_output=True, timeout=10)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Random Termux theme by day/night mode.")
    p.add_argument(
        "--mode",
        default="auto",
        choices=("auto",) + MODES,
        help="auto (detect, then --set state), or force dark/light",
    )
    p.add_argument(
        "--set",
        dest="set_mode",
        choices=MODES,
        help="record the sticky mode and exit; for automation hooks",
    )
    p.add_argument("--theme-dir", default=DEFAULT_THEME_DIR)
    p.add_argument("--dest", default=DEFAULT_DEST)
    p.add_argument("--state", default=DEFAULT_STATE)
    p.add_argument("--no-reload", action="store_true", help="write without reloading")
    p.add_argument(
        "--dry-run", action="store_true", help="report the pick without applying"
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state = pathlib.Path(args.state).expanduser()

    if args.set_mode:
        write_state(state, args.set_mode)
        eprint(f"mode: {args.set_mode}")
        return 0

    theme_dir = pathlib.Path(args.theme_dir).expanduser()
    mode = resolve_mode(args.mode, state)
    files = pool_files(theme_dir / mode)
    if not files:
        eprint(f"no themes in {theme_dir / mode}")
        return 1

    theme = choose(files, random.SystemRandom())
    if args.dry_run:
        eprint(f"would apply {mode}: {theme.stem}")
        return 0

    apply_theme(theme, pathlib.Path(args.dest).expanduser(), reload=not args.no_reload)
    eprint(f"{mode}: {theme.stem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
