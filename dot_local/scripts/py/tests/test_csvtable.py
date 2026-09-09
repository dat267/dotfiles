import unittest

import _loader

csvtable = _loader.load("csvtable")


class TestRenderTable(unittest.TestCase):
    def test_pads_columns_to_max_width(self):
        rows = [["a", "long"], ["much longer", "b"]]
        out = csvtable.render_table(rows)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        # first column width = max(len("a"), len("much longer")) = 11, pads to 11 then 2-space gap
        self.assertTrue(lines[0].startswith("a" + " " * 12 + "long"))
        self.assertEqual(lines[0].index("long"), 13)
        self.assertEqual(lines[1].index("b"), 13)

    def test_header_optional(self):
        rows = [["name", "x"], ["alice", "1"]]
        out = csvtable.render_table(rows, header=True)
        lines = out.splitlines()
        self.assertEqual(lines[0].strip(), "name   x")
        self.assertEqual(lines[1].strip(), "-----  -")
        self.assertIn("alice", lines[2])

    def test_csv_parse_with_quoted_commas(self):
        data = 'a,"hello, world",c\n1,2,3\n'
        out = csvtable.render_table([list(r) for r in csvtable.parse_csv(data)])
        self.assertIn("hello, world", out)
        self.assertIn("1", out)

    def test_custom_delimiter(self):
        data = "a;b\n1;2\n"
        out = csvtable.render_table([list(r) for r in csvtable.parse_csv(data, delimiter=";")])
        self.assertIn("a  b", out)

    def test_truncates_long_cells(self):
        rows = [["abcdefghijklmno"], ["x"]]
        out = csvtable.render_table(rows, truncate=5)
        self.assertIn("abcd…", out)
        self.assertNotIn("abcdefghi", out)

    def test_none_cells_become_empty(self):
        rows = [["a", None], ["1", "2"]]
        out = csvtable.render_table(rows)
        self.assertIn("a", out)
        self.assertIn("1", out)


if __name__ == "__main__":
    unittest.main()