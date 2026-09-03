import unittest

import _loader

project_id = _loader.load("pi-sandbox").project_id


class TestProjectId(unittest.TestCase):
    def test_prefix(self):
        self.assertTrue(project_id("/home/me/proj").startswith("pi-"))

    def test_stable(self):
        self.assertEqual(project_id("/a/b"), project_id("/a/b"))

    def test_sanitizes_separators_and_dashes(self):
        self.assertEqual(project_id("/a-b/c"), "pi-a_b_c")

    def test_lowercased(self):
        self.assertEqual(project_id("/MyProject"), "pi-myproject")

    def test_long_path_hashed(self):
        long_path = "/" + "/".join(["verylongdirectoryname"] * 6)
        pid = project_id(long_path)
        self.assertLessEqual(len(pid), 43)
        self.assertIn("_", pid[3:])

    def test_keeps_alnum_underscore_only(self):
        pid = project_id("/a b!c@d")
        self.assertTrue(all(c.isalnum() or c == "_" for c in pid[3:]))


if __name__ == "__main__":
    unittest.main()
