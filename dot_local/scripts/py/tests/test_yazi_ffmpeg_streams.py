import json
import unittest
from unittest import mock

import _loader

audio = _loader.load("yazi-ffmpeg-audio")
subtitle = _loader.load("yazi-ffmpeg-subtitle")

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
    return mock.patch.object(audio.subprocess, "run", return_value=result), mock.patch.object(
        subtitle.subprocess, "run", return_value=result
    )


class TestAudioStreams(unittest.TestCase):
    def test_filters_audio_only(self):
        p1, p2 = ffprobe_patch()
        with p1, p2:
            auds = audio.get_audio_streams("x.mkv")
        self.assertEqual(len(auds), 2)
        self.assertEqual(auds[0]["index"], 1)
        self.assertEqual(auds[0]["codec"], "aac")
        self.assertEqual(auds[0]["lang"], "jpn")
        self.assertEqual(auds[0]["title"], "Japanese 2.0")

    def test_count(self):
        p1, p2 = ffprobe_patch()
        with p1, p2:
            self.assertEqual(audio.get_audio_count("x.mkv"), 2)

    def test_ffprobe_failure_returns_empty(self):
        with mock.patch.object(audio.subprocess, "run", side_effect=OSError):
            self.assertEqual(audio.get_audio_streams("x.mkv"), [])
            self.assertEqual(audio.get_audio_count("x.mkv"), 0)


class TestSubtitleStreams(unittest.TestCase):
    def test_filters_subtitle_only(self):
        p1, p2 = ffprobe_patch()
        with p1, p2:
            subs = subtitle.get_subtitle_streams("x.mkv")
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["index"], 3)
        self.assertEqual(subs[0]["codec"], "subrip")
        self.assertEqual(subs[0]["lang"], "eng")


if __name__ == "__main__":
    unittest.main()
