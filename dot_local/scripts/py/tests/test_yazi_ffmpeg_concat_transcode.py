import unittest
from unittest import mock

import _loader

concat = _loader.load("yazi-ffmpeg-concat")
transcode = _loader.load("yazi-ffmpeg-transcode")


def run(module, argv, stdin_reply=""):
    recorded = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        return mock.Mock(returncode=0)

    with mock.patch.object(module.shutil, "which", return_value="/usr/bin/ffmpeg"), mock.patch.object(
        module.sys, "argv", ["prog"] + argv
    ), mock.patch.object(module, "input_flush", return_value=stdin_reply), mock.patch.object(
        module.subprocess, "run", side_effect=fake_run
    ):
        module.main()
    return recorded["cmd"]


class TestConcat(unittest.TestCase):
    def test_generic_files_video_filter(self):
        cmd = run(concat, ["/d/movie1.mp4", "/d/movie2.mp4"], stdin_reply="out.mp4")
        self.assertIn("concat=n=2:v=1:a=1", " ".join(cmd))
        self.assertIn("libx264", cmd)
        self.assertEqual(cmd[-1], "out.mp4")

    def test_flac_audio_only(self):
        cmd = run(concat, ["/d/a.flac", "/d/b.flac"], stdin_reply="out.flac")
        self.assertIn("concat=n=2:v=0:a=1", " ".join(cmd))
        self.assertIn("flac", cmd)
        self.assertNotIn("libx264", cmd)

    def test_generic_parent_dir_falls_back_to_first_base(self):
        cmd = run(concat, ["/home/dat/Downloads/a.flac", "/home/dat/Downloads/b.flac"], stdin_reply="")
        self.assertEqual(cmd[-1], "a_combined.flac")

    def test_named_parent_dir_used(self):
        cmd = run(concat, ["/music/album/a.flac", "/music/album/b.flac"], stdin_reply="")
        self.assertEqual(cmd[-1], "album_combined.flac")

    def test_default_ext_from_first_file(self):
        cmd = run(concat, ["/d/x.mkv", "/d/y.mkv"], stdin_reply="")
        self.assertTrue(cmd[-1].endswith(".mkv"))


class TestTranscode(unittest.TestCase):
    def test_new_extension(self):
        cmd = run(transcode, ["/d/video.avi"], stdin_reply="mp4")
        self.assertEqual(cmd, ["ffmpeg", "-i", "/d/video.avi", "-y", "/d/video.mp4"])

    def test_same_extension_gets_suffix(self):
        cmd = run(transcode, ["/d/video.mp4"], stdin_reply="mp4")
        self.assertEqual(cmd[-1], "/d/video_transcoded.mp4")

    def test_leading_dot_stripped(self):
        cmd = run(transcode, ["/d/video.avi"], stdin_reply=".mkv")
        self.assertEqual(cmd[-1], "/d/video.mkv")

    def test_extension_case_insensitive(self):
        cmd = run(transcode, ["/d/video.MP4"], stdin_reply="mp4")
        self.assertEqual(cmd[-1], "/d/video_transcoded.mp4")


if __name__ == "__main__":
    unittest.main()
