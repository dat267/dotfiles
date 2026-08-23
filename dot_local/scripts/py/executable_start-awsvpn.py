#!/usr/bin/env python3
import argparse
import os
import sys
import re
import socket
import random
import string
import subprocess
import threading
import time
import urllib.parse
import webbrowser
import signal
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

TMP_DIR = os.path.join(tempfile.gettempdir(), "awsvpnclient")
OPENVPN_LOG = os.path.join(TMP_DIR, "openvpn.log")


def print(*args, **kwargs):
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


def extract_saml_request_id(saml_url):
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
        print(f"[!] Error parsing SAMLRequest ID: {e}")
    return None


def kill_vpn_process(proc):
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


def prepare_temp_config(profile_path):
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
        print(f"[!] Error preparing temporary config: {e}")
        return profile_path


class SAMLHandler(BaseHTTPRequestHandler):
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


class SAMLServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saml_response = None
        from datetime import datetime, timezone

        self.start_time = datetime.now(timezone.utc)


def detect_paths(client_dir):
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


def parse_ovpn_profile(profile_path):
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


def resolve_endpoint_ip(hostname):
    rand_prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    try:
        return socket.gethostbyname(f"{rand_prefix}.{hostname}")
    except Exception:
        sys.exit(1)


def run():
    parser = argparse.ArgumentParser(description="Start AWS Client VPN via SAML SSO.")
    parser.add_argument('client_dir', help='AWS VPN client directory')
    parser.add_argument('ovpn_file', help='OpenVPN profile file')
    parser.add_argument('--headless', action='store_true',
                        help='Headless mode: print SAML URL, wait for pasted response')
    parser.add_argument('--saml-response-file',
                        help='Read SAML response from file (ignored without --headless)')
    args = parser.parse_args()

    client_dir = os.path.abspath(args.client_dir)
    profile = os.path.abspath(args.ovpn_file)

    global proc2
    proc2 = None

    def handle_signal(signum, frame):
        if proc2:
            kill_vpn_process(proc2)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    loader_path, openvpn_path, dns_script_path, lib_dir = detect_paths(client_dir)
    if not openvpn_path:
        print(
            f"[-] Error: acvc-openvpn binary not found under target directory: {client_dir}"
        )
        sys.exit(1)

    remote_host, remote_port, proto = parse_ovpn_profile(profile)
    if not remote_host:
        sys.exit(1)

    resolved_ip = resolve_endpoint_ip(remote_host)

    os.makedirs(TMP_DIR, exist_ok=True)
    first_stage_creds = os.path.join(TMP_DIR, "creds_stage1.txt")
    second_stage_creds = os.path.join(TMP_DIR, "creds_stage2.txt")
    temp_profile = prepare_temp_config(profile)

    server_address = ("127.0.0.1", 35001)
    try:
        httpd = SAMLServer(server_address, SAMLHandler)
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
            print(line.strip())
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
        print(f"[-] Missing authentication variables. Check full log at: {OPENVPN_LOG}")
        sys.exit(1)

    if args.headless:
        print(f"\n=== SAML login required ===")
        print(f"Open this URL in a browser on any machine:\n")
        print(f"{saml_url}\n")
        if args.saml_response_file:
            with open(args.saml_response_file) as f:
                raw_saml = f.read().strip()
            saml_response = urllib.parse.quote_plus(raw_saml, safe='')
            print(f"[+] Read SAML response from {args.saml_response_file}")
        else:
            print("After authenticating, the browser will POST to http://127.0.0.1:35001/")
            print("You can capture the SAMLResponse parameter from the POST body.")
            print("Paste the encoded SAMLResponse value below and press Ctrl+D:")
            raw_saml = sys.stdin.read().strip()
            if not raw_saml:
                print("[-] No SAML response provided.")
                sys.exit(1)
            saml_response = raw_saml.strip()
    else:
        httpd.expected_request_id = extract_saml_request_id(saml_url)
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
                    print(line.strip())
                    log_file.write(line)
                    log_file.flush()
                    if "Initialization Sequence Completed" in line:
                        connected = True
                        print(
                            "\n"
                            + "=" * 50
                            + "\n[+] AWS Client VPN CONNECTED SUCCESSFULLY!\n"
                            + "=" * 50
                        )
                        break
                    if "AUTH_FAILED" in line:
                        auth_failed_retry = True
                        kill_vpn_process(proc2)
                        break

            if connected:
                break
            if not auth_failed_retry:
                if proc2.poll() is not None and not connected:
                    print(f"[-] Connection terminated. Logs written to {OPENVPN_LOG}")
                    sys.exit(1)

        if not connected:
            sys.exit(1)

        with open(OPENVPN_LOG, "a") as log_file:
            for line in proc2.stdout:
                print(line.strip())
                log_file.write(line)
                log_file.flush()

    except KeyboardInterrupt:
        pass
    finally:
        if proc2:
            kill_vpn_process(proc2)
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
    run()
