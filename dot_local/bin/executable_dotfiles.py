#!/usr/bin/env python3
import argparse
import getpass
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime

DEFAULT_REMOTE = os.environ.get("DOTFILES_REMOTE", "")
DEFAULT_PATH = "chezmoi"


def run_cmd(args, cwd=None, dry_run=False):
    cmd_str = " ".join(args)
    if dry_run:
        print(f"[DRY-RUN] Would run: {cmd_str}")
        return True
    print(f"Running: {cmd_str}")
    try:
        subprocess.run(args, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: Command failed with exit code {e.returncode}", file=sys.stderr)
        return False


def git_has_changes(repo_path):
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return len(res.stdout.strip()) > 0
    except Exception:
        return False


def parse_listremotes(stdout):
    remotes = {}
    for line in stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            r_name = parts[0].rstrip(":")
            r_type = parts[1]
            remotes[r_name] = r_type
    return remotes


def get_remotes():
    try:
        res = subprocess.run(
            ["rclone", "listremotes", "--long"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return parse_listremotes(res.stdout)
    except (subprocess.TimeoutExpired, Exception):
        pass
    password = getpass.getpass("Enter rclone configuration password: ")
    os.environ["RCLONE_CONFIG_PASS"] = password
    try:
        res = subprocess.run(
            ["rclone", "listremotes", "--long"],
            capture_output=True,
            text=True,
            check=True,
        )
        return parse_listremotes(res.stdout)
    except Exception:
        print(
            "Error: Failed to read rclone configuration. Please check your password.",
            file=sys.stderr,
        )
        sys.exit(1)


def check_dependencies(command):
    deps = ["rclone", "chezmoi"]
    if command == "up":
        deps.append("git")
    for dep in deps:
        if not shutil.which(dep):
            print(
                f"Error: Required dependency '{dep}' is not installed or not in PATH.",
                file=sys.stderr,
            )
            sys.exit(1)


def main():
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "-r",
        "--remote",
        default=DEFAULT_REMOTE,
        required=not DEFAULT_REMOTE,
        help="Rclone remote name",
    )
    parent_parser.add_argument(
        "-p", "--path", default=DEFAULT_PATH, help="Path inside the remote"
    )
    parent_parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Preview the sync without modifying anything",
    )
    parser = argparse.ArgumentParser(
        description="Secure dotfiles synchronization wrapper."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    parser_up = subparsers.add_parser(
        "up", parents=[parent_parser], help="Sync local dotfiles to GCS (push)"
    )
    parser_up.add_argument("-m", "--message", help="Optional git commit message")
    parser_down = subparsers.add_parser(
        "down",
        parents=[parent_parser],
        help="Sync GCS dotfiles to local machine & apply (pull)",
    )
    args = parser.parse_args()
    check_dependencies(args.command)
    remotes = get_remotes()
    if args.remote not in remotes:
        print(
            f"Error: Remote '{args.remote}' not found in rclone configuration.",
            file=sys.stderr,
        )
        sys.exit(1)
    if remotes[args.remote] != "crypt":
        print(
            f"Error: Remote '{args.remote}' has type '{remotes[args.remote]}'. Only 'crypt' remotes are allowed.",
            file=sys.stderr,
        )
        sys.exit(1)
    if platform.system() == "Windows":
        local_dir = os.path.join(os.environ.get("APPDATA", ""), "chezmoi")
    else:
        local_dir = os.path.expanduser("~/.local/share/chezmoi")
    gcs_target = f"{args.remote}:{args.path}"
    if args.command == "up":
        if git_has_changes(local_dir):
            print("Detected uncommitted changes in chezmoi repository.")
            msg = (
                args.message
                or f"Auto-commit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if not run_cmd(["git", "add", "-A"], cwd=local_dir, dry_run=args.dry_run):
                sys.exit(1)
            if not run_cmd(
                ["git", "commit", "-m", msg], cwd=local_dir, dry_run=args.dry_run
            ):
                sys.exit(1)
        else:
            print("No local changes to commit.")
        rclone_args = ["rclone", "sync", local_dir, gcs_target, "-v"]
        if args.dry_run:
            rclone_args.append("--dry-run")
        if run_cmd(rclone_args):
            print("Successfully synced up to GCS!")
        else:
            sys.exit(1)
    elif args.command == "down":
        rclone_args = ["rclone", "sync", gcs_target, local_dir, "-v"]
        if args.dry_run:
            rclone_args.append("--dry-run")
        if not run_cmd(rclone_args):
            sys.exit(1)
        if not run_cmd(["chezmoi", "apply", "-v"], dry_run=args.dry_run):
            sys.exit(1)
        print("Successfully pulled and applied dotfiles!")


if __name__ == "__main__":
    main()
