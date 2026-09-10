import unittest

import _loader

split = _loader.load("yazi-ffmpeg-split")


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


if __name__ == "__main__":
    unittest.main()
