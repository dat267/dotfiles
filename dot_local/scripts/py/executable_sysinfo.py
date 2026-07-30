#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))
try:
    from _shared import COLORS, log
except ImportError:
    COLORS = {"reset": "\033[0m"}
    def log(msg, color=None):
        print(msg)


def c(text, color):
    if sys.stdout.isatty() and color:
        return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"
    return text


def get_uptime():
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        days, rem = divmod(int(secs), 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        return " ".join(parts)
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            tick = ctypes.windll.kernel32.GetTickCount64()
            secs = tick // 1000
            days, rem = divmod(secs, 86400)
            hours, rem = divmod(rem, 3600)
            mins = rem // 60
            parts = []
            if days: parts.append(f"{days}d")
            if hours: parts.append(f"{hours}h")
            parts.append(f"{mins}m")
            return " ".join(parts)
    except Exception:
        pass
    return "?"


def get_cpu_info():
    try:
        if os.path.exists("/proc/cpuinfo"):
            model = None
            cores = 0
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                    elif line.startswith("processor"):
                        cores += 1
            if model and cores:
                model = model.replace("(TM)", "™").replace("(R)", "®")
                return f"{model} ({cores} cores)"
        elif sys.platform == "win32":
            out = subprocess.run(["wmic", "cpu", "get", "name,NumberOfCores"],
                                 capture_output=True, text=True)
            lines = out.stdout.strip().splitlines()
            if len(lines) > 1:
                return lines[1].strip()
    except Exception:
        pass
    return platform.processor() or "?"


def get_mem_info():
    try:
        if os.path.exists("/proc/meminfo"):
            total = None
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1]) // 1024
            if total >= 1024:
                return f"{total // 1024} GB"
            return f"{total} MB"
        elif sys.platform == "win32":
            out = subprocess.run(["wmic", "memorychip", "get", "Capacity"],
                                 capture_output=True, text=True)
            total_bytes = 0
            for line in out.stdout.strip().splitlines()[1:]:
                line = line.strip()
                if line.isdigit():
                    total_bytes += int(line)
            if total_bytes:
                return f"{total_bytes // (1024**3)} GB"
    except Exception:
        pass
    return "?"


def get_disk_usage(path="/"):
    try:
        du = shutil.disk_usage(path)
        total_gb = du.total // (1024**3)
        used_gb = du.used // (1024**3)
        free_gb = du.free // (1024**3)
        pct = du.used * 100 // du.total
        return f"{total_gb}G total, {used_gb}G used, {free_gb}G free ({pct}%)"
    except Exception:
        return "?"


def get_ips():
    ips = []
    try:
        if sys.platform == "win32":
            out = subprocess.run(["ipconfig"], capture_output=True, text=True)
            for line in out.stdout.splitlines():
                line = line.strip()
                if "IPv4" in line or "IP Address" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        ip = parts[1].strip()
                        if ip and not ip.startswith("169.254"):
                            ips.append(ip)
        else:
            import fcntl
            SIOCGIFADDR = 0x8915
            for ifname in os.listdir("/sys/class/net"):
                if ifname == "lo":
                    continue
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    ifr = struct.pack("16sH14s", ifname.encode()[:15], socket.AF_INET, b"\x00"*14)
                    data = fcntl.ioctl(s.fileno(), SIOCGIFADDR, ifr)
                    ip = socket.inet_ntoa(data[20:24])
                    if not ip.startswith("169.254"):
                        ips.append(f"{ifname}: {ip}")
                    s.close()
                except Exception:
                    continue
        return ", ".join(ips) if ips else "?"
    except Exception:
        return "?"


def main():
    parser = argparse.ArgumentParser(prog="sysinfo", description="Display system information.")
    parser.add_argument("--short", "-s", action="store_true", help="Compact one-line output")
    args = parser.parse_args()

    os_name, arch = platform.system(), platform.machine()
    uname = platform.uname()

    if args.short:
        cpu = get_cpu_info().split("(")[0].strip()
        print(f"{os_name} {uname.release} | {cpu} | {get_mem_info()} | up {get_uptime()}")
        return

    print()
    log(f"  {'='*50}", "cyan")
    log(f"  System Information", "cyan")
    log(f"  {'='*50}", "cyan")
    print()

    items = [
        ("Host", socket.gethostname()),
        ("OS", f"{os_name} {uname.release} ({arch})"),
        ("Uptime", get_uptime()),
        ("Shell", os.path.basename(os.environ.get("SHELL", os.environ.get("ComSpec", "?")))),
        ("CPU", get_cpu_info()),
        ("RAM", get_mem_info()),
        ("Disk /", get_disk_usage("/")),
        ("IP", get_ips()),
    ]

    for label, val in items:
        print(f"  {c(label + ':', 'yellow')} {val}")

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)