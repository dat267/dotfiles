import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _loader

jsonfmt = _loader.load("jsonfmt")


class TestFormatJson(unittest.TestCase):
    def test_pretty_prints_default_indent_2(self):
        out = jsonfmt.format_json('{"a":1,"b":[1,2]}')
        self.assertEqual(out, '{\n  "a": 1,\n  "b": [\n    1,\n    2\n  ]\n}')

    def test_custom_indent(self):
        out = jsonfmt.format_json('{"a":1}', indent=4)
        self.assertEqual(out, '{\n    "a": 1\n}')

    def test_minify(self):
        out = jsonfmt.format_json('{\n  "a": 1,\n  "b": [1, 2]\n}', minify=True)
        self.assertEqual(out, '{"a":1,"b":[1,2]}')

    def test_sort_keys(self):
        out = jsonfmt.format_json('{"b":1,"a":2}', sort_keys=True)
        self.assertEqual(out, '{\n  "a": 2,\n  "b": 1\n}')

    def test_invalid_json_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            jsonfmt.format_json("{not json}")


class TestMain(unittest.TestCase):
    def test_stdin_pipeline(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = jsonfmt.main(argv=["--minify"], stdin=io.StringIO('{"x": 1}'))
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), '{"x":1}\n')

    def test_file_argument(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"y": 2}')
            path = f.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = jsonfmt.main(argv=[path], stdin=io.StringIO())
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue()), {"y": 2})
        finally:
            os.unlink(path)

    def test_parse_error_exits_1_with_stderr(self):
        err = io.StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                jsonfmt.main(argv=[], stdin=io.StringIO("{bad"))
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("error", err.getvalue().lower())


if __name__ == "__main__":
    unittest.main()