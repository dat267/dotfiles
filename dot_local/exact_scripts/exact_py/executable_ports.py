#!/usr/bin/env python3
"""List listening sockets and flag what the network can reach.

Wraps `ss -tlnp`, classifies every listener as:
  exposed  — bound to a wildcard (0.0.0.0 / [::]), reachable from the network
  bound    — bound to one specific interface address
  local    — loopback only (127.x / [::1])

Process names come from ss; without root, only your own processes resolve.
"""

import argparse
import os
import re
import subprocess
import sys

USE_COLOR = sys.stderr.isatty() or sys.stdout.isatty()
NO_COLOR = "NO_COLOR" in os.environ


def eprint(*args):
    print(*args, file=sys.stderr)


def _c(code, s):
    if USE_COLOR and not NO_COLOR:
        return f"\033[{code}m{s}\033[0m"
    return s


def parse_ss(text):
    """Parse `ss -tlnp` output into rows: proto, addr, port, process."""
    rows = []
    for line in text.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 4 or parts[0] != "LISTEN":
            continue
        proto, _rq, _sq, local = parts[0], parts[1], parts[2], parts[3]
        addr, port = split_addr_port(local)
        if port is None:
            continue
        process = ""
        if len(parts) == 6:
            m = re.search(r'\(\s*"([^"]+)"', parts[5])
            if m:
                process = m.group(1)
        rows.append({"proto": proto, "addr": addr, "port": port, "process": process})
    return rows


def split_addr_port(local):
    """Split '127.0.0.53%lo:53' or '[::]:22' into (addr, port)."""
    if local.startswith("["):
        host, sep, rest = local.partition("]")
        if not sep or ":" not in rest:
            return host.lstrip("["), None
        return host.lstrip("["), int(rest[1:])
    host, sep, port = local.rpartition(":")
    if not sep:
        return local, None
    host = host.split("%")[0]
    try:
        return host, int(port)
    except ValueError:
        return host, None


def classify(addr):
    """exposed (wildcard) | local (loopback) | bound (one interface)."""
    if addr in ("0.0.0.0", "::", "*"):
        return "exposed"
    if addr == "::1" or addr.startswith("127."):
        return "local"
    return "bound"


LABELS = {"exposed": ("91", "EXPOSED"), "bound": ("93", "bound"), "local": ("90", "local")}


def render(rows, width=76):
    """Sorted table: PORT  LABEL  ADDRESS  PROCESS."""
    lines = []
    for r in sorted(rows, key=lambda r: (r["port"], r["addr"])):
        code, label = LABELS[classify(r["addr"])]
        addr = r["addr"]
        if classify(addr) != "exposed":
            addr = f"{addr}:{r['port']}"
        proc = r["process"] or "-"
        line = f"{r['port']:>5}  {_c(code, f'{label:<8}')}  {addr:<{width - 20}}  {proc}"
        lines.append(line.rstrip())
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-e", "--exposed", action="store_true",
                        help="only wildcard-bound (network-reachable) listeners")
    args = parser.parse_args(argv)

    try:
        res = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        eprint("ss(8) not found — iproute2 required")
        return 1
    except subprocess.CalledProcessError as e:
        eprint(f"ss failed: {e.stderr.strip()}")
        return 1

    rows = parse_ss(res.stdout)
    if args.exposed:
        rows = [r for r in rows if classify(r["addr"]) == "exposed"]
    out = render(rows)
    if out:
        print("\n".join(out))
    else:
        eprint("no matching listeners")
    return 0


if __name__ == "__main__":
    sys.exit(main())
