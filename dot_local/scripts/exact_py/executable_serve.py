#!/usr/bin/env python3
"""Serve a directory (or single file) over the LAN, with a scannable QR code.

  serve .                     # share the current directory
  serve ~/shot.png            # share one file
  serve logs --upload         # let the other device send files back
  serve . --token             # require a one-time token in the URL
  serve artifact.tar --once   # exit after a single completed transfer

Binds all interfaces so phones and other machines on the network can connect;
prints every usable URL plus an ASCII QR code for the first one. Standard
library only; the QR code is rendered with `qrencode` when available and
skipped otherwise.
"""

import argparse
import html
import http.server
import mimetypes
import os
import secrets
import socket
import string
import subprocess
import sys
import threading
import urllib.parse

DEFAULT_PORT = 8000
PORT_TRIES = 20


def eprint(*args):
    print(*args, file=sys.stderr)


def safe_join(root, url_path):
    """Resolve a URL path inside `root`; return None when it escapes.

    Accepts percent-encoded input, rejects absolute paths and any traversal
    that leaves the root, and returns the real path otherwise.
    """
    decoded = urllib.parse.unquote(url_path or "/")
    decoded = decoded.replace("\\", "/")
    parts = [p for p in decoded.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None
    target = os.path.realpath(os.path.join(root, *parts))
    if target != root and not target.startswith(root + os.sep):
        return None
    return target


def make_server(root, host="0.0.0.0", port=DEFAULT_PORT, upload=False, token=None, once=False, only=None):
    """Build a ThreadingHTTPServer serving `root`; port 0 picks any free port.

    `only` restricts sharing to one filename inside `root`, so serving a single
    file never exposes its siblings.
    """
    root = os.path.realpath(root)
    handler = _make_handler(root, upload=upload, token=token, only=only)
    server = http.server.ThreadingHTTPServer((host, port), handler)
    server.exit_after_request = once
    return server


def bind_server(root, host="0.0.0.0", port=DEFAULT_PORT, tries=1, **kwargs):
    """Bind the first free port in `port`..`port + tries - 1`, else re-raise."""
    last_error = None
    for candidate in range(port, port + max(tries, 1)):
        try:
            return make_server(root, host, candidate, **kwargs)
        except OSError as exc:
            last_error = exc
    raise last_error


def _make_handler(root, upload=False, token=None, only=None):
    class Handler(http.server.SimpleHTTPRequestHandler):
        server_version = "serve/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            eprint(f"  {self.address_string()} {fmt % args}")

        def _token_ok(self):
            if not token:
                return True
            supplied = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("t", [""])[0]
            return secrets.compare_digest(supplied, token)

        def _requested_path(self):
            """URL path with the query stripped and the shared-file shorthand applied."""
            raw = urllib.parse.urlsplit(self.path).path
            if only and raw in ("", "/"):
                return "/" + only
            return raw

        def _only_allows(self):
            return only is None or self._requested_path() == "/" + only

        def send_head(self):
            if not self._token_ok():
                self.send_error(403, "Forbidden")
                return None
            if not self._only_allows():
                self.send_error(404, "Not found")
                return None
            path = self.translate_path(self.path)
            if path is None:
                self.send_error(403, "Forbidden")
                return None
            if os.path.isdir(path):
                return self._send_listing(path)
            if not os.path.exists(path):
                self.send_error(404, "Not found")
                return None
            try:
                fh = open(path, "rb")
            except OSError:
                self.send_error(404, "Not found")
                return None
            size = os.fstat(fh.fileno()).st_size
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.end_headers()
            return fh

        def translate_path(self, path):
            """Resolve within root, ignoring the query string."""
            raw = urllib.parse.urlsplit(path).path
            if only and raw in ("", "/"):
                raw = "/" + only
            return safe_join(root, raw)

        def _send_listing(self, path):
            entries = sorted(os.listdir(path))
            rows = []
            for name in entries:
                full = os.path.join(path, name)
                is_dir = os.path.isdir(full)
                label = html.escape(name + ("/" if is_dir else ""))
                href = urllib.parse.quote(name + ("/" if is_dir else ""))
                size = "" if is_dir else f" <span>{human_size(os.path.getsize(full))}</span>"
                rows.append(f'<li><a href="{href}">{label}</a>{size}</li>')
            form = ""
            if upload:
                form = (
                    '<form method="post" action="/__upload" enctype="multipart/form-data">'
                    '<input type="file" name="file"><button>upload</button></form>'
                )
            body = (
                "<!doctype html><meta charset=utf-8><title>serve</title>"
                f"<h1>{html.escape(os.path.relpath(path, root) or '.')}</h1>"
                f"{form}<ul>{''.join(rows)}</ul>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None

        def do_POST(self):
            if not upload:
                self.send_error(403, "Uploads disabled")
                return
            if not self._token_ok():
                self.send_error(403, "Forbidden")
                return
            if urllib.parse.urlsplit(self.path).path != "/__upload":
                self.send_error(404, "Not found")
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            filename, content = parse_multipart(ctype, body)
            if filename is None:
                self.send_error(400, "No file field")
                return
            target = safe_join(root, "/" + os.path.basename(filename))
            if target is None:
                self.send_error(400, "Bad filename")
                return
            with open(target, "wb") as fh:
                fh.write(content)
            eprint(f"  uploaded {os.path.basename(target)} ({human_size(len(content))})")
            self.send_response(201)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
            if getattr(self.server, "exit_after_request", False):
                threading_shutdown(self.server)

        def copyfile(self, source, outputfile):
            try:
                super().copyfile(source, outputfile)
            finally:
                if getattr(self.server, "exit_after_request", False):
                    threading_shutdown(self.server)

    return Handler


def threading_shutdown(server):
    """Stop the server from a handler thread without deadlocking shutdown()."""
    threading.Thread(target=server.shutdown, daemon=True).start()


def human_size(nbytes):
    """Format a byte count for humans (1.4 KB, 3.2 MB)."""
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def parse_multipart(content_type, body):
    """Extract (filename, content) from a multipart/form-data body.

    Minimal parser for the single `file` field browsers send; returns
    (None, b"") when the field is absent or the body is malformed.
    """
    marker = "boundary="
    if marker not in (content_type or ""):
        return None, b""
    boundary = content_type.split(marker, 1)[1].strip().strip('"')
    if not boundary:
        return None, b""
    delimiter = b"--" + boundary.encode()
    for part in body.split(delimiter):
        if b"\r\n\r\n" not in part:
            continue
        raw_headers, _, content = part.partition(b"\r\n\r\n")
        filename = None
        for line in raw_headers.decode("utf-8", "replace").splitlines():
            if not line.lower().startswith("content-disposition:"):
                continue
            for field in line.split(";"):
                field = field.strip()
                if field.startswith("filename="):
                    filename = field.split("=", 1)[1].strip().strip('"')
        if not filename:
            continue
        if content.endswith(b"\r\n"):
            content = content[:-2]
        return os.path.basename(filename), content
    return None, b""


def guess_lan_ips():
    """Return LAN IPv4 addresses for this host, loopback and link-local removed."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except socket.gaierror:
        pass
    # The UDP connect trick reveals the address used for outbound traffic.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 9))
            ips.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def format_urls(ips, port, share_path="", token=None):
    """Build the printable URLs, LAN addresses first, localhost last."""
    query = f"?t={token}" if token else ""
    path = urllib.parse.quote(share_path.lstrip("/"))
    suffix = f"/{path}" if path else "/"
    urls = [f"http://{ip}:{port}{suffix}{query}" for ip in ips]
    urls.append(f"http://localhost:{port}{suffix}{query}")
    return urls


def render_qr(url):
    """Return an ASCII QR code for `url`, or None when qrencode is missing."""
    try:
        out = subprocess.run(
            ["qrencode", "-t", "ANSIUTF8", "-o", "-", url],
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return out.stdout.decode(errors="replace").rstrip("\n")


def new_token(length=8):
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="serve",
        description="Serve a directory or file over the LAN with a QR code.",
    )
    parser.add_argument("path", nargs="?", default=".", help="directory or file to share")
    parser.add_argument("--port", type=int, default=None, help=f"port (default {DEFAULT_PORT}, auto-increments when busy)")
    parser.add_argument("--bind", default="0.0.0.0", help="address to bind (default all interfaces)")
    parser.add_argument("--upload", action="store_true", help="allow the other device to upload files")
    parser.add_argument("--once", action="store_true", help="exit after the first completed transfer")
    parser.add_argument("--token", nargs="?", const="", default=None, help="require a token; value generated when omitted")
    parser.add_argument("--no-qr", action="store_true", help="do not print a QR code")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    target = os.path.realpath(os.path.expanduser(args.path))
    if not os.path.exists(target):
        eprint(f"serve: no such path: {args.path}")
        return 1
    if os.path.isfile(target):
        root, share_path, only = os.path.dirname(target), os.path.basename(target), os.path.basename(target)
    else:
        root, share_path, only = target, "", None

    token = new_token() if args.token == "" else (args.token or None)
    tries = 1 if args.port is not None else PORT_TRIES
    start = args.port if args.port is not None else DEFAULT_PORT
    try:
        server = bind_server(root, args.bind, start, tries=tries, upload=args.upload, token=token, once=args.once, only=only)
    except OSError as exc:
        eprint(f"serve: cannot bind {args.bind}:{start} ({exc})")
        return 1
    port = server.server_address[1]
    urls = format_urls(guess_lan_ips(), port, share_path, token)
    eprint(f"serving {os.path.relpath(target, os.getcwd()) or target}")
    for url in urls:
        eprint(f"  {url}")
    if token:
        eprint("  (token required: ?t=...)")
    if args.upload:
        eprint("  uploads enabled")
    if not args.no_qr:
        qr = render_qr(urls[0])
        if qr:
            eprint("")
            eprint(qr)
    eprint("\nCtrl-C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        eprint("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
