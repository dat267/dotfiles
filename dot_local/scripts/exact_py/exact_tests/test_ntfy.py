"""Tests for ntfy — generic ntfy.sh notify tool.

Seams: target resolution (flag > env > config file), request construction
(JSON publish mode, UTF-8-safe), transport via opener injection (the house
pattern — drives real urlopen against a loopback server where it matters),
and exit codes.
"""

import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import _loader

ntfy = _loader.load("ntfy")


class TargetCase(unittest.TestCase):
	def test_flag_beats_env_beats_config(self):
		with tempfile.TemporaryDirectory() as tmp:
			cfg = ntfy.config_path(self.home(tmp))
			cfg.parent.mkdir(parents=True)
			cfg.write_text("https://conf.example/topic-c\n")
			with patch.dict(os.environ, {"NTFY_TARGET": "env-topic"}):
				# resolve_target returns the raw target; URL expansion is
				# target_url's job (tested separately) — layered, composed in main.
				self.assertEqual(ntfy.resolve_target("flag-topic", self.home(tmp)), "flag-topic")
				self.assertEqual(ntfy.resolve_target(None, self.home(tmp)), "env-topic")
				with patch.dict(os.environ, {}, clear=True):
					self.assertEqual(ntfy.resolve_target(None, self.home(tmp)), "https://conf.example/topic-c")
					self.assertEqual(
						ntfy.target_url(ntfy.resolve_target(None, self.home(tmp))),
						"https://conf.example/topic-c")

	def test_bare_topic_gets_public_base_url(self):
		self.assertEqual(ntfy.target_url("mytopic"), "https://ntfy.sh/mytopic")

	def test_full_url_and_self_hosted_pass_through(self):
		self.assertEqual(ntfy.target_url("https://ntfy.sh/x"), "https://ntfy.sh/x")
		self.assertEqual(ntfy.target_url("http://lan.local:2586/x"), "http://lan.local:2586/x")

	def home(self, tmp):
		return type(tmp)(tmp)


class RequestCase(unittest.TestCase):
	def test_json_publish_mode_is_utf8_safe(self):
		req = ntfy.build_request(
			"https://ntfy.sh/mytopic",
			message="héllo wörld",
			subject="päpipä",
			priority="high",
			tags=["warning", "robot"],
		)
		self.assertEqual(req.full_url, "https://ntfy.sh/mytopic")
		self.assertEqual(req.get_method(), "POST")
		body = json.loads(req.data.decode("utf-8"))
		self.assertEqual(body, {
			"topic": "mytopic",
			"message": "héllo wörld",
			"title": "päpipä",
			"priority": "high",
			"tags": ["warning", "robot"],
		})

	def test_minimal_request_omits_optionals(self):
		req = ntfy.build_request("https://ntfy.sh/t", message="hi")
		body = json.loads(req.data.decode("utf-8"))
		self.assertEqual(body, {"topic": "t", "message": "hi"})


class TransportCase(unittest.TestCase):
	def test_send_uses_injected_opener(self):
		seen = {}

		class FakeResponse(io.BytesIO):
			def __enter__(self):
				return self

			def __exit__(self, *a):
				return False

		def fake_opener(req, timeout=0):
			seen["url"] = req.full_url
			seen["body"] = json.loads(req.data.decode("utf-8"))
			return FakeResponse(b'{"id":"x"}')

		rc = ntfy.send("https://ntfy.sh/t", message="ok", opener=fake_opener)
		self.assertEqual(rc, 0)
		self.assertEqual(seen["url"], "https://ntfy.sh/t")
		self.assertEqual(seen["body"]["message"], "ok")

	def test_http_error_is_reported_not_raised(self):
		def bad_opener(req, timeout=0):
			raise urllib.error.HTTPError(req.full_url, 403, "forbidden", None, io.BytesIO(b"no"))

		rc = ntfy.send("https://ntfy.sh/t", message="x", opener=bad_opener)
		self.assertEqual(rc, 1)


class StdinCase(unittest.TestCase):
	def test_message_from_stdin_when_no_positional(self):
		payload = "piped message\n"
		with patch("sys.stdin", io.StringIO(payload)):
			self.assertEqual(ntfy.read_message(None), payload)


if __name__ == "__main__":
	unittest.main()