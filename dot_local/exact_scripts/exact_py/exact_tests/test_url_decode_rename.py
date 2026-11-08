import os
import tempfile
import unittest

import _loader

udr = _loader.load("url_decode_rename")


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

    def test_scans_the_directory_argument_not_the_cwd(self):
        """`directory` used to be listed but names were renamed relative to the
        CWD, so any non-'.' argument raised FileNotFoundError."""
        sub = os.path.join(self.tmp, "sub")
        os.makedirs(sub)
        open(os.path.join(sub, "x%21.txt"), "w").close()
        udr.rename_files(sub)
        self.assertTrue(os.path.exists(os.path.join(sub, "x!.txt")))
        self.assertFalse(os.path.exists(os.path.join(sub, "x%21.txt")))
        self.assertFalse(
            os.path.exists(os.path.join(self.tmp, "x!.txt")),
            "the rename landed in the CWD instead of the target directory",
        )

    def test_encoded_separator_is_not_decoded_into_a_path(self):
        """%2F decodes to '/', which would move the file out of the directory."""
        open(os.path.join(self.tmp, "a%2Fb.txt"), "w").close()
        udr.rename_files(self.tmp)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a%2Fb.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "a", "b.txt")))


if __name__ == "__main__":
    unittest.main()
