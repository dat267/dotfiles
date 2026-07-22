#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import getpass
import platform
import shutil
import subprocess
from datetime import datetime

DEFAULT_REMOTE = os.environ.get("DOTFILES_REMOTE", "")
DEFAULT_PATH = "chezmoi"


def run_cmd(args, cwd=None, dry_run=False):
    cmd_str = " ".join(args)
    if dry_run:
        click.echo(f"[DRY-RUN] Would run: {cmd_str}")
        return True
    click.echo(f"Running: {cmd_str}")
    try:
        subprocess.run(args, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: Command failed with exit code {e.returncode}", err=True)
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
        click.echo(
            "Error: Failed to read rclone configuration. Please check your password.",
            err=True,
        )
        raise SystemExit(1)


def check_dependencies(command):
    deps = ["rclone", "chezmoi"]
    if command == "up":
        deps.append("git")
    for dep in deps:
        if not shutil.which(dep):
            click.echo(
                f"Error: Required dependency '{dep}' is not installed or not in PATH.",
                err=True,
            )
            raise SystemExit(1)


@click.group()
@click.option("-r", "--remote", default=DEFAULT_REMOTE, help="Rclone remote name", required=not DEFAULT_REMOTE)
@click.option("-p", "--path", default=DEFAULT_PATH, help="Path inside the remote")
@click.option("-d", "--dry-run", is_flag=True, help="Preview the sync without modifying anything")
@click.pass_context
def cli(ctx, remote, path, dry_run):
    """Secure dotfiles synchronization wrapper."""
    ctx.ensure_object(dict)
    ctx.obj["remote"] = remote
    ctx.obj["path"] = path
    ctx.obj["dry_run"] = dry_run


@cli.command()
@click.option("-m", "--message", help="Optional git commit message")
@click.pass_context
def up(ctx, message):
    """Sync local dotfiles to GCS (push)"""
    remote = ctx.obj["remote"]
    path = ctx.obj["path"]
    dry_run = ctx.obj["dry_run"]
    check_dependencies("up")
    remotes = get_remotes()
    if remote not in remotes:
        click.echo(
            f"Error: Remote '{remote}' not found in rclone configuration.",
            err=True,
        )
        raise SystemExit(1)
    if remotes[remote] != "crypt":
        click.echo(
            f"Error: Remote '{remote}' has type '{remotes[remote]}'. Only 'crypt' remotes are allowed.",
            err=True,
        )
        raise SystemExit(1)
    if platform.system() == "Windows":
        local_dir = os.path.join(os.environ.get("APPDATA", ""), "chezmoi")
    else:
        local_dir = os.path.expanduser("~/.local/share/chezmoi")
    gcs_target = f"{remote}:{path}"
    if git_has_changes(local_dir):
        click.echo("Detected uncommitted changes in chezmoi repository.")
        msg = (
            message
            or f"Auto-commit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if not run_cmd(["git", "add", "-A"], cwd=local_dir, dry_run=dry_run):
            raise SystemExit(1)
        if not run_cmd(
            ["git", "commit", "-m", msg], cwd=local_dir, dry_run=dry_run
        ):
            raise SystemExit(1)
    else:
        click.echo("No local changes to commit.")
    rclone_args = ["rclone", "sync", local_dir, gcs_target, "-v"]
    if dry_run:
        rclone_args.append("--dry-run")
    if run_cmd(rclone_args):
        click.echo("Successfully synced up to GCS!")
    else:
        raise SystemExit(1)


@cli.command()
@click.pass_context
def down(ctx):
    """Sync GCS dotfiles to local machine & apply (pull)"""
    remote = ctx.obj["remote"]
    path = ctx.obj["path"]
    dry_run = ctx.obj["dry_run"]
    check_dependencies("down")
    remotes = get_remotes()
    if remote not in remotes:
        click.echo(
            f"Error: Remote '{remote}' not found in rclone configuration.",
            err=True,
        )
        raise SystemExit(1)
    if remotes[remote] != "crypt":
        click.echo(
            f"Error: Remote '{remote}' has type '{remotes[remote]}'. Only 'crypt' remotes are allowed.",
            err=True,
        )
        raise SystemExit(1)
    if platform.system() == "Windows":
        local_dir = os.path.join(os.environ.get("APPDATA", ""), "chezmoi")
    else:
        local_dir = os.path.expanduser("~/.local/share/chezmoi")
    gcs_target = f"{remote}:{path}"
    rclone_args = ["rclone", "sync", gcs_target, local_dir, "-v"]
    if dry_run:
        rclone_args.append("--dry-run")
    if not run_cmd(rclone_args):
        raise SystemExit(1)
    if not run_cmd(["chezmoi", "apply", "-v"], dry_run=dry_run):
        raise SystemExit(1)
    click.echo("Successfully pulled and applied dotfiles!")


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
