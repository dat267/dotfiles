import os
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
    def test_gb_above_threshold(self):
        data = "MemTotal:       32768000 kB\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=data)):
            self.assertEqual(sysinfo.get_mem_info(), "31 GB")

    def test_mb_below_threshold(self):
        data = "MemTotal:       512000 kB\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=data)):
            self.assertEqual(sysinfo.get_mem_info(), "500 MB")

    def test_unknown_on_error(self):
        with mock.patch("builtins.open", side_effect=OSError):
            with mock.patch.object(sysinfo.os.path, "exists", return_value=False):
                self.assertEqual(sysinfo.get_mem_info(), "?")


class TestGetDiskUsage(unittest.TestCase):
    def test_format(self):
        result = sysinfo.get_disk_usage(os.path.expanduser("~"))
        self.assertRegex(result, r"^\d+G total, \d+G used, \d+G free \(\d+%\)$")


class TestCFunction(unittest.TestCase):
    def test_no_color_when_not_tty(self):
        with mock.patch.object(sysinfo.sys.stdout, "isatty", return_value=False):
            self.assertEqual(sysinfo.c("text", "yellow"), "text")


if __name__ == "__main__":
    unittest.main()
