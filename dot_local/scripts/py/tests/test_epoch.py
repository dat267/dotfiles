import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

import _loader

epoch = _loader.load("epoch")


class TestToIso(unittest.TestCase):
    def test_epoch_to_local_iso_roundtrip(self):
        # 2024-01-02 03:04:05 UTC -> any local representation must re-parse to same instant
        ts = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc).timestamp()
        iso = epoch.to_iso(ts)
        reparsed = datetime.fromisoformat(iso.replace(" ", "T", 1))
        self.assertEqual(reparsed.timestamp(), int(ts))  # second precision

    def test_epoch_to_utc_iso(self):
        iso = epoch.to_iso(0, utc=True)
        self.assertEqual(iso, "1970-01-01 00:00:00")

    def test_epoch_utc_roundtrip_with_fraction(self):
        iso = epoch.to_iso(0.5, utc=True)
        self.assertEqual(iso, "1970-01-01 00:00:00.500000")


class TestParseIso(unittest.TestCase):
    def test_parses_space_separator(self):
        ts = epoch.parse_iso("2024-01-02 03:04:05")
        self.assertEqual(datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"), "2024-01-02 03:04:05")

    def test_parses_t_separator(self):
        ts = epoch.parse_iso("2024-01-02T03:04:05")
        self.assertEqual(datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"), "2024-01-02 03:04:05")

    def test_parses_utc_zulu(self):
        ts = epoch.parse_iso("1970-01-01T00:00:00Z")
        self.assertEqual(ts, 0)

    def test_parses_utc_offset(self):
        ts = epoch.parse_iso("1970-01-01T02:00:00+02:00")
        self.assertEqual(ts, 0)

    def test_invalid_raises_valueerror(self):
        with self.assertRaises(ValueError):
            epoch.parse_iso("not a date")


class TestMain(unittest.TestCase):
    def test_no_args_prints_now_epoch(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = epoch.main(argv=[])
        self.assertEqual(rc, 0)
        self.assertTrue(buf.getvalue().strip().isdigit())

    def test_epoch_arg_prints_iso(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            epoch.main(argv=["0"])
        self.assertIn("1970-01-01", buf.getvalue())

    def test_parse_flag_prints_epoch(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            epoch.main(argv=["-p", "1970-01-01T00:00:00Z"])
        self.assertEqual(buf.getvalue().strip(), "0")

    def test_utc_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            epoch.main(argv=["-u", "0"])
        self.assertEqual(buf.getvalue().strip(), "1970-01-01 00:00:00")


if __name__ == "__main__":
    unittest.main()