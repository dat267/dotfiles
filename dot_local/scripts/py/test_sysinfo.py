#!/usr/bin/env python3
"""Tests for sysinfo.py — run with: python3 -m pytest test_sysinfo.py"""
import ctypes
import fcntl
import os
import platform
import shutil
import socket
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import executable_sysinfo as s


def test_c():
    assert s.c("hello", "yellow") == "\033[93mhello\033[0m"
    assert s.c("plain", None) == "plain"


def test_get_uptime_linux(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda _: iter(["123456.78 99999.99\n"]))
    monkeypatch.setattr(sys, "platform", "linux")
    assert s.get_uptime() == "1d 10h 17m"


def test_get_uptime_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    class FakeKernel32:
        @staticmethod
        def GetTickCount64():
            return 86400000

    monkeypatch.setattr(ctypes, "windll", type("o", (), {"kernel32": FakeKernel32()})())
    assert s.get_uptime() == "1d 0h 0m"


def test_get_uptime_windows_short(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    class FakeKernel32:
        @staticmethod
        def GetTickCount64():
            return 3600000

    monkeypatch.setattr(ctypes, "windll", type("o", (), {"kernel32": FakeKernel32()})())
    assert s.get_uptime() == "1h 0m"


def test_get_uptime_fallback(monkeypatch):
    monkeypatch.setattr(sys, "platform", "unknown")
    assert s.get_uptime() == "?"


def test_get_cpu_info_linux(monkeypatch):
    cpuinfo = "\n".join([
        "processor\t: 0",
        "model name\t: ARMv8 Processor rev 4",
        "processor\t: 1",
        "model name\t: ARMv8 Processor rev 4",
    ])
    monkeypatch.setattr("os.path.exists", lambda p: p == "/proc/cpuinfo")
    monkeypatch.setattr("builtins.open", lambda *a, **kw: iter(cpuinfo.splitlines(True)))
    assert s.get_cpu_info() == "ARMv8 Processor rev 4 (2 cores)"


def test_get_cpu_info_no_proc(monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "processor", lambda: "arm64")
    assert s.get_cpu_info() == "arm64"


def test_get_mem_info_linux(monkeypatch):
    meminfo = "MemTotal:       8123456 kB\n"
    monkeypatch.setattr("os.path.exists", lambda p: p == "/proc/meminfo")
    monkeypatch.setattr("builtins.open", lambda *a, **kw: iter(meminfo.splitlines(True)))
    assert s.get_mem_info() == "7 GB"


def test_get_mem_info_windows(monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    monkeypatch.setattr(sys, "platform", "win32")

    class FakeProc:
        stdout = "Capacity\n8589934592\n8589934592\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeProc())
    assert s.get_mem_info() == "16 GB"


def test_get_disk_usage(monkeypatch):
    class FakeUsage:
        total = 256 * 1024 ** 3
        used = 128 * 1024 ** 3
        free = 128 * 1024 ** 3

    monkeypatch.setattr(shutil, "disk_usage", lambda p: FakeUsage())
    assert s.get_disk_usage("/") == "256G total, 128G used, 128G free (50%)"


def test_get_ips_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("os.listdir", lambda p: ["eth0", "lo"])

    fake_ioctl = lambda *a: b"\x00" * 20 + socket.inet_aton("192.168.1.1") + b"\x00" * 10
    monkeypatch.setattr(fcntl, "ioctl", fake_ioctl)
    ips = s.get_ips()
    assert "192.168.1.1" in ips
    assert "eth0" in ips


def test_main_short(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sysinfo", "--short"])
    monkeypatch.setattr(s, "get_uptime", lambda: "1h")
    monkeypatch.setattr(s, "get_cpu_info", lambda: "ARM (4 cores)")
    monkeypatch.setattr(s, "get_mem_info", lambda: "8 GB")
    s.main()
    out = capsys.readouterr().out
    assert "up 1h" in out


def test_main_long(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sysinfo"])

    monkeypatch.setattr(socket, "gethostname", lambda: "testbox")
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(platform, "uname", lambda: type("U", (), {"release": "6.1.0"})())
    monkeypatch.setattr(s, "get_uptime", lambda: "2h")
    monkeypatch.setattr(s, "get_cpu_info", lambda: "Intel (2 cores)")
    monkeypatch.setattr(s, "get_mem_info", lambda: "16 GB")
    monkeypatch.setattr(s, "get_disk_usage", lambda p: "256G total, 50% used")
    monkeypatch.setattr(s, "get_ips", lambda: "192.168.1.1")
    s.main()
    out = capsys.readouterr().out
    assert "testbox" in out
    assert "Linux" in out
    assert "Intel" in out