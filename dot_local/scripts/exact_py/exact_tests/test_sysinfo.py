import os
import sys
import tempfile
import unittest
from unittest import mock

import _loader

sysinfo = _loader.load("sysinfo")


class TestGetUptime(unittest.TestCase):
    def test_parses_proc_uptime(self):
        data = "90061.5 180000\n"  # 1d 1h 1m 1s
        with mock.patch("builtins.open", mock.mock_open(read_data=data)):
            self.assertEqual(sysinfo.get_uptime(), "1d 1h 1m")

    def test_omits_zero_days_and_hours(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="600 1200\n")):
            self.assertEqual(sysinfo.get_uptime(), "10m")

    def test_fallback_when_proc_missing(self):
        with mock.patch("builtins.open", side_effect=OSError), mock.patch.object(
            sysinfo.subprocess,
            "run",
            return_value=mock.Mock(returncode=0, stdout="up 2 days, 3:15"),
        ):
            self.assertEqual(sysinfo.get_uptime(), "2 days, 3:15")


class TestGetMemInfo(unittest.TestCase):
    # The /proc branch is Linux-only; Windows takes the wmic branch. Pin the
    # probe so the expectation is about parsing, not about the host.
    def test_gb_above_threshold(self):
        data = "MemTotal:       32768000 kB\n"
        with mock.patch.object(sysinfo.os.path, "exists", return_value=True), \
                mock.patch("builtins.open", mock.mock_open(read_data=data)):
            self.assertEqual(sysinfo.get_mem_info(), "31 GB")

    def test_mb_below_threshold(self):
        data = "MemTotal:       512000 kB\n"
        with mock.patch.object(sysinfo.os.path, "exists", return_value=True), \
                mock.patch("builtins.open", mock.mock_open(read_data=data)):
            self.assertEqual(sysinfo.get_mem_info(), "500 MB")

    def test_unknown_on_error(self):
        with mock.patch("builtins.open", side_effect=OSError), \
                mock.patch.object(sysinfo.os.path, "exists", return_value=False), \
                mock.patch.object(sysinfo.subprocess, "run",
                                  return_value=mock.Mock(returncode=1, stdout="")):
            self.assertEqual(sysinfo.get_mem_info(), "?")


class TestGetDiskUsage(unittest.TestCase):
    def test_format(self):
        result = sysinfo.get_disk_usage(os.path.expanduser("~"))
        self.assertRegex(result, r"^\d+G total, \d+G used, \d+G free \(\d+%\)$")


class TestCFunction(unittest.TestCase):
    def test_no_color_when_not_tty(self):
        with mock.patch.object(sysinfo.sys.stdout, "isatty", return_value=False):
            self.assertEqual(sysinfo.c("text", "yellow"), "text")


class TestGetIps(unittest.TestCase):
    """Android denies /sys/class/net and /proc/net, so the interface walk
    yields nothing there. get_ips() must then fall back to the kernel-chosen
    egress address (a connected UDP socket sends no packets, needs no root)."""

    def setUp(self):
        # get_ips() branches on sys.platform; pin it so these exercise the
        # sysfs/egress helper patch on every host (CI runs Windows).
        patcher = mock.patch.object(sysinfo.sys, "platform", "linux")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sysfs_interfaces_win_when_readable(self):
        with mock.patch.object(sysinfo, "_interface_ips",
                               return_value=["wlan0: 10.0.0.2"]), \
                mock.patch.object(sysinfo, "_egress_ip") as egress:
            self.assertEqual(sysinfo.get_ips(), "wlan0: 10.0.0.2")
        egress.assert_not_called()

    def test_falls_back_to_egress_ip_when_sysfs_empty(self):
        with mock.patch.object(sysinfo, "_interface_ips", return_value=[]), \
                mock.patch.object(sysinfo, "_egress_ip", return_value="192.168.1.12"):
            self.assertEqual(sysinfo.get_ips(), "192.168.1.12")

    def test_unknown_when_no_interface_and_no_egress(self):
        with mock.patch.object(sysinfo, "_interface_ips", return_value=[]), \
                mock.patch.object(sysinfo, "_egress_ip", return_value=None):
            self.assertEqual(sysinfo.get_ips(), "?")

    def test_link_local_egress_rejected(self):
        with mock.patch.object(sysinfo, "_interface_ips", return_value=[]), \
                mock.patch.object(sysinfo, "_egress_ip", return_value="169.254.1.1"):
            self.assertEqual(sysinfo.get_ips(), "?")

    def test_interface_ips_swallows_permission_error(self):
        with mock.patch.object(sysinfo.os, "listdir", side_effect=PermissionError):
            self.assertEqual(sysinfo._interface_ips(), [])

    def test_interface_ips_swallows_missing_fcntl(self):
        with mock.patch.dict(sys.modules, {"fcntl": None}):
            self.assertEqual(sysinfo._interface_ips(), [])


class TestEgressIp(unittest.TestCase):
    def test_reports_socket_local_address(self):
        fake = mock.Mock()
        fake.getsockname.return_value = ("192.168.1.12", 45678)
        with mock.patch.object(sysinfo.socket, "socket", return_value=fake):
            self.assertEqual(sysinfo._egress_ip(), "192.168.1.12")
        fake.connect.assert_called_once()
        fake.close.assert_called_once()

    def test_none_on_oserror(self):
        fake = mock.Mock()
        fake.connect.side_effect = OSError("network is unreachable")
        with mock.patch.object(sysinfo.socket, "socket", return_value=fake):
            self.assertIsNone(sysinfo._egress_ip())
        fake.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
