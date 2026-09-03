import os
import tempfile
import unittest

import _loader

udr = _loader.load("url-decode-rename")


class TestRenameFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_decodes_percent_escapes(self):
        open("my%20file.txt", "w").close()
        udr.rename_files(".")
        self.assertTrue(os.path.exists("my file.txt"))
        self.assertFalse(os.path.exists("my%20file.txt"))

    def test_skips_existing_target(self):
        open("a%20b.txt", "w").close()
        open("a b.txt", "w").close()
        udr.rename_files(".")
        self.assertTrue(os.path.exists("a%20b.txt"), "source must survive on conflict")
        self.assertTrue(os.path.exists("a b.txt"))

    def test_ignores_files_without_percent(self):
        open("plain.txt", "w").close()
        udr.rename_files(".")
        self.assertTrue(os.path.exists("plain.txt"))

    def test_scans_current_directory(self):
        # NOTE: rename_files() lists files under `directory` but renames them
        # relative to the CWD, so only the default "." usage works.
        sub = os.path.join(self.tmp, "sub")
        os.makedirs(sub)
        open(os.path.join(sub, "x%21.txt"), "w").close()
        os.chdir(sub)
        udr.rename_files(".")
        self.assertTrue(os.path.exists(os.path.join(sub, "x!.txt")))


if __name__ == "__main__":
    unittest.main()
