#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import getpass
import json
import platform
import random
import re
import shutil
import signal
import socket
import string
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

COLORS = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "reset": "\033[0m",
}


def log(message, color=None):
    use_color = sys.stdout.isatty() and (os.name == "posix" or os.environ.get("TERM"))
    if color and use_color:
        click.echo(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        click.echo(message)


@click.group()
def cli():
    pass


# --- build ---

BASE_SRC_DIR = os.path.expanduser("~/.local/src")


@cli.command()
def build():
    if not os.path.isdir(BASE_SRC_DIR):
        log(f"Error: Base directory not found at {BASE_SRC_DIR}", "red")
        raise SystemExit(1)

    log(f"Scanning for projects with Makefiles under {BASE_SRC_DIR}...", "cyan")

    build_targets = []
    for root, _, files in os.walk(BASE_SRC_DIR):
        if "Makefile" in files or "makefile" in files:
            build_targets.append(root)

    if not build_targets:
        log("No projects containing a Makefile were found.", "yellow")
        return

    success_count = 0
    failed_count = 0

    for target_dir in sorted(build_targets):
        display_name = os.path.relpath(target_dir, BASE_SRC_DIR)
        log(f"Building: {display_name}", "cyan")

        try:
            subprocess.run(["make", "-C", target_dir, "build"], check=True)
            log(f"Built {display_name} successfully", "green")
            success_count += 1
        except subprocess.CalledProcessError:
            log(f"Failed to build {display_name}", "red")
            failed_count += 1
        except FileNotFoundError:
            log("Error: 'make' tool is missing from the host system.", "red")
            sys.exit(1)

    log(
        f"Compilation batch complete. Passed: {success_count}, Failed: {failed_count}",
        "green" if failed_count == 0 else "yellow",
    )


# --- uninstall ---

_TOOLS_REPO = "dat267/dotfiles"
INSTALL_DIR = os.path.expanduser("~/.local/bin")


def _uninstall_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system in ("linux", "android"):
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "darwin"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        raise SystemExit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


@cli.command()
def uninstall():
    os_name, arch_name = _uninstall_platform()

    suffix = f"-{os_name}-{arch_name}"
    if os_name == "windows":
        suffix += ".exe"

    url = f"https://api.github.com/repos/{_TOOLS_REPO}/releases"
    log(f"Fetching latest tools release from {_TOOLS_REPO}...", "cyan")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            releases = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        log(f"Error fetching releases: {e}", "red")
        sys.exit(1)

    tools_releases = [r for r in releases if r.get("tag_name", "").startswith("max/")]
    if not tools_releases:
        log("Error: No release found.", "red")
        sys.exit(1)

    tools_releases.sort(key=lambda r: r.get("created_at", ""))
    latest_release = tools_releases[-1]
    tag = latest_release["tag_name"]
    log(f"Latest release: {tag}", "green")

    assets = latest_release.get("assets", [])
    matching_assets = [a for a in assets if a.get("name", "").endswith(suffix)]

    if not matching_assets:
        log(
            f"No tools found for {os_name}/{arch_name} in {tag} \u2014 nothing to uninstall.",
            "yellow",
        )
        raise SystemExit(0)

    for asset in matching_assets:
        asset_name = asset["name"]
        tool_name = asset_name[: -len(suffix)]
        binary_name = tool_name
        if os_name == "windows":
            binary_name += ".exe"

        dest_path = os.path.join(INSTALL_DIR, binary_name)

        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
                log(f"Removed {dest_path}", "green")
            except Exception as e:
                log(f"Error removing {dest_path}: {e}", "red")
        else:
            log(f"{dest_path} not found \u2014 skipping", "yellow")

    log("Done.", "green")


# --- url-decode ---

def _url_decode_rename_files(directory="."):
    for f in os.listdir(directory):
        if "%" not in f:
            continue

        new_name = urllib.parse.unquote(f)

        if os.path.exists(new_name):
            click.echo(f"skip: {f} -> {new_name} (exists)")
            continue

        click.echo(f"{f} -> {new_name}")
        os.rename(f, new_name)


@cli.command()
@click.argument("directory", default=".")
def url_decode(directory):
    """Rename files by decoding URL-encoded characters."""
    _url_decode_rename_files(directory)


# --- cloudsh ---

@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("ssh_args", nargs=-1)
def cloudsh(ssh_args):
    gcloud = shutil.which("gcloud")
    if not gcloud:
        click.echo("gcloud not found", err=True)
        raise SystemExit(1)

    port_pattern = r"-[pP]\s([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|6553[0-5])"
    addr_pattern = r"\S*@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"

    out = subprocess.check_output(
        [gcloud, "cloud-shell", "ssh", "--dry-run", "--authorize-session"], text=True
    )

    m = re.search(port_pattern, out)
    if not m:
        click.echo("Tunnel port not found", err=True)
        raise SystemExit(1)
    port = m.group(1)

    m = re.search(addr_pattern, out)
    if not m:
        click.echo("SSH address not found", err=True)
        raise SystemExit(1)
    addr = m.group(0)

    key = os.path.join(os.path.expanduser("~"), ".ssh", "google_compute_engine")
    if not os.path.exists(key):
        click.echo("Private key does not exist!", err=True)
        raise SystemExit(1)

    cmd = [
        "ssh",
        "-t",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "LogLevel=ERROR",
        "-p",
        port,
        "-i",
        key,
        addr,
        " ".join(ssh_args),
    ]

    click.echo(f"Trying to SSH into {addr}, tunnel port {port}...")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


# --- dotfiles ---

DEFAULT_REMOTE = os.environ.get("DOTFILES_REMOTE", "")
DEFAULT_PATH = "chezmoi"


def _df_run_cmd(args, cwd=None, dry_run=False):
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


def _df_git_has_changes(repo_path):
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


def _df_parse_listremotes(stdout):
    remotes = {}
    for line in stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            r_name = parts[0].rstrip(":")
            r_type = parts[1]
            remotes[r_name] = r_type
    return remotes


def _df_get_remotes():
    try:
        res = subprocess.run(
            ["rclone", "listremotes", "--long"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return _df_parse_listremotes(res.stdout)
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
        return _df_parse_listremotes(res.stdout)
    except Exception:
        click.echo(
            "Error: Failed to read rclone configuration. Please check your password.",
            err=True,
        )
        raise SystemExit(1)


def _df_check_dependencies(command):
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


@cli.group()
@click.option("-r", "--remote", default=DEFAULT_REMOTE, help="Rclone remote name", required=not DEFAULT_REMOTE)
@click.option("-p", "--path", default=DEFAULT_PATH, help="Path inside the remote")
@click.option("-d", "--dry-run", is_flag=True, help="Preview the sync without modifying anything")
@click.pass_context
def dotfiles(ctx, remote, path, dry_run):
    """Secure dotfiles synchronization wrapper."""
    ctx.ensure_object(dict)
    ctx.obj["remote"] = remote
    ctx.obj["path"] = path
    ctx.obj["dry_run"] = dry_run


@dotfiles.command()
@click.option("-m", "--message", help="Optional git commit message")
@click.pass_context
def up(ctx, message):
    """Sync local dotfiles to GCS (push)"""
    remote = ctx.obj["remote"]
    path = ctx.obj["path"]
    dry_run = ctx.obj["dry_run"]
    _df_check_dependencies("up")
    remotes = _df_get_remotes()
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
    if _df_git_has_changes(local_dir):
        click.echo("Detected uncommitted changes in chezmoi repository.")
        msg = (
            message
            or f"Auto-commit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if not _df_run_cmd(["git", "add", "-A"], cwd=local_dir, dry_run=dry_run):
            raise SystemExit(1)
        if not _df_run_cmd(
            ["git", "commit", "-m", msg], cwd=local_dir, dry_run=dry_run
        ):
            raise SystemExit(1)
    else:
        click.echo("No local changes to commit.")
    rclone_args = ["rclone", "sync", local_dir, gcs_target, "-v"]
    if dry_run:
        rclone_args.append("--dry-run")
    if _df_run_cmd(rclone_args):
        click.echo("Successfully synced up to GCS!")
    else:
        raise SystemExit(1)


@dotfiles.command()
@click.pass_context
def down(ctx):
    """Sync GCS dotfiles to local machine & apply (pull)"""
    remote = ctx.obj["remote"]
    path = ctx.obj["path"]
    dry_run = ctx.obj["dry_run"]
    _df_check_dependencies("down")
    remotes = _df_get_remotes()
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
    if not _df_run_cmd(rclone_args):
        raise SystemExit(1)
    if not _df_run_cmd(["chezmoi", "apply", "-v"], dry_run=dry_run):
        raise SystemExit(1)
    click.echo("Successfully pulled and applied dotfiles!")


# --- hello ---

@cli.command()
def hello():
    click.echo("Hello World!")


# --- start-vpn ---

TMP_DIR = os.path.join(tempfile.gettempdir(), "awsvpnclient")
OPENVPN_LOG = os.path.join(TMP_DIR, "openvpn.log")


def _vpn_print(*args, **kwargs):
    import builtins

    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    msg = sep.join(map(str, args))
    if file in (sys.stdout, sys.stderr):
        lines = msg.split("\n")
        msg = "\n".join("\r" + line for line in lines)
        if end == "\n":
            end = "\r\n"
    builtins.print(msg, end=end, sep="", file=file, flush=True)


def _vpn_extract_saml_request_id(saml_url):
    try:
        import zlib
        import base64

        parsed = urllib.parse.urlparse(saml_url)
        query = urllib.parse.parse_qs(parsed.query)
        saml_request_b64 = query.get("SAMLRequest", [""])[0]
        if not saml_request_b64:
            return None
        compressed = base64.b64decode(saml_request_b64)
        xml_data = None
        for wbits in [-zlib.MAX_WBITS, zlib.MAX_WBITS, zlib.MAX_WBITS + 16]:
            try:
                xml_data = zlib.decompress(compressed, wbits).decode(
                    "utf-8", errors="ignore"
                )
                break
            except Exception:
                continue
        if not xml_data:
            xml_data = compressed.decode("utf-8", errors="ignore")
        match = re.search(r'ID=["\']([^"\']+)["\']', xml_data)
        if match:
            return match.group(1)
    except Exception as e:
        _vpn_print(f"[!] Error parsing SAMLRequest ID: {e}")
    return None


def _vpn_kill_process(proc):
    if not proc or proc.poll() is not None:
        return
    try:
        pids = (
            subprocess.check_output(["pgrep", "-P", str(proc.pid)])
            .decode()
            .strip()
            .split()
        )
        for pid in pids:
            subprocess.run(
                ["sudo", "kill", "-9", pid],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass
    try:
        subprocess.run(
            ["sudo", "kill", "-9", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.wait(timeout=2)
    except Exception:
        pass


def _vpn_prepare_temp_config(profile_path):
    temp_profile_path = os.path.join(TMP_DIR, "temp_vpn.conf")
    try:
        with open(profile_path, "r") as f:
            lines = f.readlines()
        with open(temp_profile_path, "w") as f:
            for line in lines:
                if line.strip() == "nobind":
                    continue
                f.write(line)
        return temp_profile_path
    except Exception as e:
        _vpn_print(f"[!] Error preparing temporary config: {e}")
        return profile_path


class _SAMLHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        body_str = post_data.decode("utf-8")
        parsed_data = urllib.parse.parse_qs(body_str)
        saml_response_list = parsed_data.get("SAMLResponse") or parsed_data.get(
            "samlresponse"
        )
        if not saml_response_list:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"SAMLResponse field is empty or does not exist")
            return
        self.raw_encoded_saml = None
        match_raw = re.search(r"(?:SAMLResponse|samlresponse)=([^&]+)", body_str)
        if match_raw:
            self.raw_encoded_saml = match_raw.group(1).strip()
        saml_response = saml_response_list[0].strip()
        if not self.raw_encoded_saml:
            self.raw_encoded_saml = urllib.parse.quote_plus(saml_response)

        import base64
        from datetime import datetime, timezone, timedelta

        try:
            decoded = base64.b64decode(saml_response).decode("utf-8", errors="ignore")
            in_response_to = None
            rt_match = re.search(r'InResponseTo=["\']([^"\']+)["\']', decoded)
            if rt_match:
                in_response_to = rt_match.group(1)
            expected = getattr(self.server, "expected_request_id", None)
            if expected and in_response_to and in_response_to != expected:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Mismatched session")
                return
            match = re.search(r'IssueInstant=["\']([^"\']+)["\']', decoded)
            if match:
                issue_instant = match.group(1)
                ts_str = issue_instant.replace("Z", "+00:00")
                issue_time = datetime.fromisoformat(ts_str)
                if issue_time < (self.server.start_time - timedelta(seconds=15)):
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Expired token")
                    return
        except Exception:
            pass

        self.server.saml_response = self.raw_encoded_saml
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        success_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AWS VPN SSO Login Success</title>
            <style>
                body { font-family: sans-serif; background: #1e3c72; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; color: #333; }
                .card { background: white; padding: 40px; border-radius: 16px; text-align: center; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Authentication Success!</h1>
                <p>Your AWS Client VPN SAML login has been completed successfully.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(success_html.encode("utf-8"))
        threading.Thread(target=self.server.shutdown).start()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Active")


class _SAMLServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saml_response = None
        from datetime import datetime, timezone

        self.start_time = datetime.now(timezone.utc)


def _vpn_detect_paths(client_dir):
    base_vpn = os.path.join(client_dir, "Service/Resources/openvpn")
    if not os.path.exists(base_vpn):
        base_vpn = client_dir

    loader = os.path.join(base_vpn, "ld-musl-x86_64.so.1")
    openvpn = os.path.join(base_vpn, "acvc-openvpn")
    if sys.platform == "win32" and not os.path.exists(openvpn):
        openvpn = os.path.join(base_vpn, "acvc-openvpn.exe")
    dns = os.path.join(base_vpn, "configure-dns")

    return (
        loader if os.path.exists(loader) else None,
        openvpn if os.path.exists(openvpn) else None,
        dns if os.path.exists(dns) else None,
        base_vpn,
    )


def _vpn_parse_ovpn_profile(profile_path):
    remote_host = None
    remote_port = 1194
    proto = "udp"
    if not os.path.exists(profile_path):
        sys.exit(1)
    with open(profile_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or line.startswith(";"):
                continue
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "remote":
                if len(parts) > 1:
                    remote_host = parts[1]
                if len(parts) > 2:
                    try:
                        remote_port = int(parts[2])
                    except ValueError:
                        pass
            elif parts[0] == "proto":
                if len(parts) > 1:
                    proto = "tcp" if "tcp" in parts[1].lower() else "udp"
    return remote_host, remote_port, proto


def _vpn_resolve_endpoint_ip(hostname):
    rand_prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    try:
        return socket.gethostbyname(f"{rand_prefix}.{hostname}")
    except Exception:
        sys.exit(1)


@cli.command()
@click.argument("aws_client_dir", type=click.Path(exists=True))
@click.argument("ovpn_file", type=click.Path(exists=True))
def start_vpn(aws_client_dir, ovpn_file):
    """Connect to AWS Client VPN via SAML authentication."""
    client_dir = os.path.abspath(aws_client_dir)
    profile = os.path.abspath(ovpn_file)

    global proc2
    proc2 = None

    def handle_signal(signum, frame):
        if proc2:
            _vpn_kill_process(proc2)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    loader_path, openvpn_path, dns_script_path, lib_dir = _vpn_detect_paths(client_dir)
    if not openvpn_path:
        _vpn_print(
            f"[-] Error: acvc-openvpn binary not found under target directory: {client_dir}"
        )
        sys.exit(1)

    remote_host, remote_port, proto = _vpn_parse_ovpn_profile(profile)
    if not remote_host:
        sys.exit(1)

    resolved_ip = _vpn_resolve_endpoint_ip(remote_host)

    os.makedirs(TMP_DIR, exist_ok=True)
    first_stage_creds = os.path.join(TMP_DIR, "creds_stage1.txt")
    second_stage_creds = os.path.join(TMP_DIR, "creds_stage2.txt")
    temp_profile = _vpn_prepare_temp_config(profile)

    server_address = ("127.0.0.1", 35001)
    try:
        httpd = _SAMLServer(server_address, _SAMLHandler)
    except OSError:
        sys.exit(1)

    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    with open(first_stage_creds, "w", newline="\n") as f:
        f.write("N/A\nACS::35001\n")

    env = os.environ.copy()
    if lib_dir and sys.platform.startswith("linux"):
        env["LD_LIBRARY_PATH"] = lib_dir

    cmd_stage1 = []
    if loader_path:
        cmd_stage1.append(loader_path)
    cmd_stage1.append(openvpn_path)
    cmd_stage1.extend(
        [
            "--config",
            temp_profile,
            "--verb",
            "4",
            "--proto",
            proto,
            "--remote",
            resolved_ip,
            str(remote_port),
            "--auth-user-pass",
            first_stage_creds,
        ]
    )

    proc = subprocess.Popen(
        cmd_stage1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    pattern = re.compile(
        r"AUTH_FAILED,CRV1:([^:]+):([^:]+):([^:]+):(https?://[^\s\']+)"
    )
    vpn_sid, saml_url = None, None

    with open(OPENVPN_LOG, "w") as log_file:
        for line in proc.stdout:
            _vpn_print(line.strip())
            log_file.write(line)
            log_file.flush()
            match = pattern.search(line)
            if match:
                vpn_sid = match.group(2)
                saml_url = match.group(4)
                break
            if line.startswith("CHALLENGE:"):
                saml_url = line.replace("CHALLENGE:", "").strip()

    proc.terminate()
    proc.wait()

    if not vpn_sid or not saml_url:
        _vpn_print(f"[-] Missing authentication variables. Check full log at: {OPENVPN_LOG}")
        sys.exit(1)

    httpd.expected_request_id = _vpn_extract_saml_request_id(saml_url)
    try:
        webbrowser.open(saml_url)
    except Exception:
        pass

    try:
        while httpd.saml_response is None:
            time.sleep(0.2)
    except KeyboardInterrupt:
        sys.exit(1)

    saml_response = httpd.saml_response
    with open(second_stage_creds, "w", newline="\n") as f:
        f.write(f"N/A\nCRV1::{vpn_sid}::{saml_response}\n")

    cmd_stage2 = []
    if sys.platform != "win32":
        cmd_stage2.extend(["sudo", "env"])
        if lib_dir and sys.platform.startswith("linux"):
            cmd_stage2.append(f"LD_LIBRARY_PATH={lib_dir}")
    if loader_path:
        cmd_stage2.append(loader_path)
    cmd_stage2.append(openvpn_path)

    local_source_port = random.randint(40000, 60000)
    cmd_stage2.extend(
        [
            "--config",
            temp_profile,
            "--verb",
            "4",
            "--proto",
            proto,
            "--remote",
            resolved_ip,
            str(remote_port),
            "--lport",
            str(local_source_port),
            "--auth-nocache",
        ]
    )
    if dns_script_path:
        cmd_stage2.extend(
            [
                "--script-security",
                "2",
                "--up",
                dns_script_path,
                "--down",
                dns_script_path,
                "--up-restart",
                "--down-pre",
            ]
        )
    cmd_stage2.extend(["--auth-user-pass", second_stage_creds])

    connected = False
    try:
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                local_source_port = random.randint(40000, 60000)
                try:
                    cmd_stage2[cmd_stage2.index("--lport") + 1] = str(local_source_port)
                except ValueError:
                    pass

            proc2 = subprocess.Popen(
                cmd_stage2,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            auth_failed_retry = False

            with open(OPENVPN_LOG, "a") as log_file:
                for line in proc2.stdout:
                    _vpn_print(line.strip())
                    log_file.write(line)
                    log_file.flush()
                    if "Initialization Sequence Completed" in line:
                        connected = True
                        _vpn_print(
                            "\n"
                            + "=" * 50
                            + "\n[+] AWS Client VPN CONNECTED SUCCESSFULLY!\n"
                            + "=" * 50
                        )
                        break
                    if "AUTH_FAILED" in line:
                        auth_failed_retry = True
                        _vpn_kill_process(proc2)
                        break

            if connected:
                break
            if not auth_failed_retry:
                if proc2.poll() is not None and not connected:
                    _vpn_print(f"[-] Connection terminated. Logs written to {OPENVPN_LOG}")
                    sys.exit(1)

        if not connected:
            sys.exit(1)

        with open(OPENVPN_LOG, "a") as log_file:
            for line in proc2.stdout:
                _vpn_print(line.strip())
                log_file.write(line)
                log_file.flush()

    except KeyboardInterrupt:
        pass
    finally:
        if proc2:
            _vpn_kill_process(proc2)
        for path in [
            first_stage_creds,
            second_stage_creds,
            os.path.join(TMP_DIR, "temp_vpn.conf"),
        ]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
