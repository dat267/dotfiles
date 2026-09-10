import io
import tempfile
import unittest
from unittest import mock

import _loader

yt = _loader.load("yazi-translate")


class TestGuessLang(unittest.TestCase):
    def test_cjk(self):
        self.assertEqual(yt._guess_lang("こんにちは世界テストです" * 2), "ja")

    def test_korean(self):
        self.assertEqual(yt._guess_lang("안녕하세요테스트" * 2), "ko")

    def test_cyrillic(self):
        self.assertEqual(yt._guess_lang("приветмиртесткод" * 2), "ru")

    def test_default_english(self):
        self.assertEqual(yt._guess_lang("hello world"), "en")


class TestUrlSize(unittest.TestCase):
    def test_ascii_short(self):
        self.assertLess(yt._url_size("hello"), yt._UA_LIMIT)

    def test_cjk_expands(self):
        text = "あ" * 300  # 900 utf-8 bytes -> ~2700 encoded chars
        self.assertGreater(yt._url_size(text), yt._UA_LIMIT)


class TestDetectEncoding(unittest.TestCase):
    def test_utf8(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write("héllo".encode("utf-8"))
            path = f.name
        try:
            self.assertEqual(yt._detect_encoding(path), "utf-8")
        finally:
            import os

            os.remove(path)

    def test_latin1_fallback(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"\xff\xfe abc")
            path = f.name
        try:
            # not valid utf-8/shift_jis/euc-jp in general -> decodes as latin-1
            self.assertIn(yt._detect_encoding(path), ("latin-1", "cp932", "shift_jis"))
        finally:
            import os

            os.remove(path)


class TestTranslateChunking(unittest.TestCase):
    def test_short_text_single_call(self):
        with mock.patch.object(yt, "_translate_one", return_value="x") as t:
            self.assertEqual(yt.translate("hi", "en"), "x")
            t.assert_called_once_with("hi", "en", "auto")

    def test_long_text_chunked(self):
        calls = []

        def fake_one(text, target, source):
            calls.append(text)
            return text.upper()

        line = "a" * 2000  # one line exceeds the chunk budget once encoded
        with mock.patch.object(yt, "_translate_one", side_effect=fake_one):
            result = yt.translate("\n".join([line, line, line]), "en")
        self.assertEqual(len(calls), 3)
        self.assertEqual(result.count("\n"), 2)


class TestTranslateOneFallback(unittest.TestCase):
    @staticmethod
    def _fail(name):
        def fn(text, target, source):
            raise ValueError("boom")
        fn.__name__ = name
        return fn

    def test_falls_back_to_second_provider(self):
        with mock.patch.object(yt, "translate_lingva", self._fail("lingva")), mock.patch.object(
            yt, "translate_mymemory", return_value="ok"
        ) as mm:
            self.assertEqual(yt._translate_one("hi", "en", "de"), "ok")
            mm.assert_called_once_with("hi", "en", "de")

    def test_auto_mode_guesses_source_for_mymemory(self):
        with mock.patch.object(yt, "translate_lingva", self._fail("lingva")), mock.patch.object(
            yt, "translate_mymemory", return_value="ok"
        ) as mm:
            yt._translate_one("приветмиртесткод", "en", "auto")
            self.assertEqual(mm.call_args.args[2], "ru")

    def test_all_fail_raises(self):
        with mock.patch.object(yt, "translate_lingva", self._fail("lingva")), mock.patch.object(
            yt, "translate_mymemory", self._fail("mymemory")
        ):
            with self.assertRaises(RuntimeError):
                yt._translate_one("hi", "en", "de")


if __name__ == "__main__":
    unittest.main()
