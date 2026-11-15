import sys
import unittest
from unittest import mock

import _loader

split = _loader.load("yazi_ffmpeg_split")


class TestParseTs(unittest.TestCase):
    def test_hms(self):
        self.assertEqual(split.parse_ts("1:02:03"), 3723)

    def test_ms(self):
        self.assertEqual(split.parse_ts("5:30"), 330)

    def test_seconds_only(self):
        self.assertEqual(split.parse_ts("42"), 42.0)

    def test_float_seconds(self):
        self.assertEqual(split.parse_ts("1.5"), 1.5)

    def test_whitespace_tolerant(self):
        self.assertEqual(split.parse_ts(" 0:01:00.5 "), 60.5)


class TestInvalidInput(unittest.TestCase):
    """A typo in the timestamps reached float() and killed the script with a
    traceback instead of a message, which is exactly the input a person types."""

    def test_a_typo_reports_instead_of_raising(self):
        runs = []
        with mock.patch.object(split.shutil, "which", return_value="ffmpeg"), \
                mock.patch.object(split.os.path, "exists", return_value=True), \
                mock.patch.object(split, "input_flush", side_effect=["0:30, 1:0a", ""]), \
                mock.patch.object(split.subprocess, "run", lambda cmd, **kw: runs.append(cmd)), \
                mock.patch("builtins.input", return_value=""), \
                mock.patch.object(sys, "argv", ["split", "/tmp/movie.mkv"]):
            split.main()
        self.assertEqual(runs, [], "nothing may be split from an invalid list")

    def test_points_are_split_from_rejected_entries(self):
        pts, bad = split.parse_points("0:30, 1:0a, 2:00")
        self.assertEqual(pts, [30.0, 120.0])
        self.assertEqual(bad, ["1:0a"])


if __name__ == "__main__":
    unittest.main()
