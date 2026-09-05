import json
import unittest
from unittest import mock

import _loader

streams = _loader.load("yazi-ffmpeg-streams")

FFPROBE_JSON = json.dumps(
    {
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264"},
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "tags": {"language": "jpn", "title": "Japanese 2.0"},
            },
            {
                "index": 2,
                "codec_type": "audio",
                "codec_name": "flac",
                "tags": {"language": "eng"},
            },
            {"index": 3, "codec_type": "subtitle", "codec_name": "subrip", "tags": {"language": "eng"}},
        ]
    }
)


def ffprobe_patch():
    result = mock.Mock(stdout=FFPROBE_JSON)
    return mock.patch.object(streams.subprocess, "run", return_value=result)


class TestGetStreams(unittest.TestCase):
    def test_filters_audio_only(self):
        with ffprobe_patch():
            auds = streams.get_streams("x.mkv", "audio")
        self.assertEqual(len(auds), 2)
        self.assertEqual(auds[0]["index"], 1)
        self.assertEqual(auds[0]["codec"], "aac")
        self.assertEqual(auds[0]["lang"], "jpn")
        self.assertEqual(auds[0]["title"], "Japanese 2.0")

    def test_filters_subtitle_only(self):
        with ffprobe_patch():
            subs = streams.get_streams("x.mkv", "subtitle")
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["index"], 3)
        self.assertEqual(subs[0]["codec"], "subrip")
        self.assertEqual(subs[0]["lang"], "eng")

    def test_count(self):
        with ffprobe_patch():
            self.assertEqual(streams.get_stream_count("x.mkv", "audio"), 2)
            self.assertEqual(streams.get_stream_count("x.mkv", "subtitle"), 1)

    def test_ffprobe_failure_returns_empty(self):
        with mock.patch.object(streams.subprocess, "run", side_effect=OSError):
            self.assertEqual(streams.get_streams("x.mkv", "audio"), [])
            self.assertEqual(streams.get_stream_count("x.mkv", "audio"), 0)


class TestPromoteStream(unittest.TestCase):
    def test_mkvmerge_used_for_mkv(self):
        probe = mock.Mock(stdout=FFPROBE_JSON)
        merger = mock.Mock(returncode=0)
        with mock.patch.object(streams.shutil, "which", return_value="/usr/bin/mkvmerge"), mock.patch.object(
            streams.subprocess, "run", side_effect=[probe, merger]
        ) as run, mock.patch.object(streams.os, "replace"):
            ok = streams.promote_stream("x.mkv", "audio", 1)
        self.assertTrue(ok)
        ffprobe_cmd = run.call_args_list[0][0][0]
        self.assertEqual(ffprobe_cmd[:5], ["ffprobe", "-v", "quiet", "-print_format", "json"])
        merge_cmd = run.call_args_list[1][0][0]
        self.assertEqual(merge_cmd[0], "mkvmerge")

    def test_ffmpeg_fallback_cmd_audio(self):
        count = mock.Mock(return_value=3)
        with mock.patch.object(streams.shutil, "which", return_value=None), mock.patch.object(
            streams, "get_stream_count", count
        ), mock.patch.object(streams.subprocess, "run") as run, mock.patch.object(streams.os, "replace"):
            ok = streams.promote_stream("x.mkv", "audio", 1)
        self.assertTrue(ok)
        cmd = run.call_args_list[0][0][0]
        self.assertEqual(
            cmd,
            [
                "ffmpeg", "-y", "-i", "x.mkv",
                "-map", "0:v",
                "-map", "0:a:1",
                "-map", "0:a:0",
                "-map", "0:a:2",
                "-map", "0:s?",
                "-c", "copy",
                "-disposition:a:0", "default",
                "x.mkv.reorder.mkv",
            ],
        )

    def test_ffmpeg_fallback_cmd_subtitle(self):
        count = mock.Mock(return_value=2)
        with mock.patch.object(streams.shutil, "which", return_value=None), mock.patch.object(
            streams, "get_stream_count", count
        ), mock.patch.object(streams.subprocess, "run") as run, mock.patch.object(streams.os, "replace"):
            ok = streams.promote_stream("x.mkv", "subtitle", 1)
        self.assertTrue(ok)
        cmd = run.call_args_list[0][0][0]
        self.assertEqual(
            cmd,
            [
                "ffmpeg", "-y", "-i", "x.mkv",
                "-map", "0:v",
                "-map", "0:a",
                "-map", "0:s:1",
                "-map", "0:s:0",
                "-c", "copy",
                "-disposition:s:0", "default",
                "x.mkv.reorder.mkv",
            ],
        )

    def test_needs_two_tracks(self):
        count = mock.Mock(return_value=1)
        with mock.patch.object(streams.shutil, "which", return_value=None), mock.patch.object(
            streams, "get_stream_count", count
        ), mock.patch.object(streams.subprocess, "run") as run:
            ok = streams.promote_stream("x.mp4", "audio", 0)
        self.assertFalse(ok)
        run.assert_not_called()


if __name__ == "__unittest__":
    unittest.main()
