#!/usr/bin/env python3
"""ntfy — send push notifications via ntfy.sh (or any ntfy server).

Generic on purpose: any agent, script, or cron job can call it. Body comes
from a positional arg or stdin, so piping works:

    ntfy -s "task done" "the build finished, 0 failures"
    ./slow-job.sh | ntfy -s "slow-job output" -
    echo "disk 91%" | ntfy -p high -s "disk alert"

Target precedence: --topic flag > $NTFY_TARGET > ~/.config/ntfy/target.
A bare topic name publishes to ntfy.sh; a full URL (self-hosted servers
included) is used as-is. Publishes in JSON mode — UTF-8-safe subjects and
tags with no header-escaping traps.

The topic name (or URL path) is a bearer secret: anyone who knows it can
send. Keep it out of agent-writable config if the channel matters.

Run: ntfy [-s SUBJECT] [-p PRIORITY] [-t TOPIC] [--tag TAG]... [MESSAGE]
     ntfy --print-topic  # mint a fresh crypto-secure URL + setup recipe
"""

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

PUBLIC_BASE = "https://ntfy.sh/"
CONFIG_PATH = Path("~/.config/ntfy/target").expanduser()
TIMEOUT = 30

PRIORITIES = ("min", "low", "default", "high", "urgent", "1", "2", "3", "4", "5")


def config_path(home: Path | None = None) -> Path:
	"""Per-user target file, relative to HOME so tests can redirect it."""
	if home:
		return Path(home) / ".config/ntfy/target"
	return Path("~/.config/ntfy/target").expanduser()


def resolve_target(flag_value: str | None, home: Path | None = None) -> str:
	"""flag > $NTFY_TARGET > ~/.config/ntfy/target (single line)."""
	if flag_value:
		return flag_value
	env = os.environ.get("NTFY_TARGET")
	if env:
		return env
	cfg = config_path(home)
	if cfg.is_file():
		value = cfg.read_text(encoding="utf-8").strip()
		if value:
			return value
	raise SystemExit(
		"no target: pass --topic, set $NTFY_TARGET, or write the topic/URL "
		f"to {cfg} (one line)"
	)


def target_url(target: str) -> str:
	"""Bare topic → ntfy.sh; anything URL-shaped passes through untouched."""
	if "://" in target:
		return target
	return PUBLIC_BASE + target.lstrip("/")


def build_request(url: str, *, message: str, subject=None, priority=None, tags=None):
	"""JSON publish mode: one POST, UTF-8 end to end."""
	payload = {"topic": url.rsplit("/", 1)[-1] or url, "message": message}
	if subject:
		payload["title"] = subject
	if priority:
		payload["priority"] = str(priority)
	if tags:
		payload["tags"] = list(tags)
	req = urllib.request.Request(url, method="POST")
	req.add_header("Content-Type", "application/json")
	req.data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
	return req


def send(url: str, *, message: str, subject=None, priority=None, tags=None, opener=None) -> int:
	"""POST and return a process exit code; HTTP errors are reported, not raised."""
	req = build_request(url, message=message, subject=subject, priority=priority, tags=tags)
	try:
		if opener:
			with opener(req, timeout=TIMEOUT) as resp:
				resp.read()
		else:
			with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
				resp.read()
	except urllib.error.HTTPError as error:
		detail = error.read().decode("utf-8", "replace").strip()[:200]
		print(f"ntfy: HTTP {error.code} from {url}: {detail or error.reason}", file=sys.stderr)
		return 1
	except (urllib.error.URLError, OSError) as error:
		print(f"ntfy: {error}", file=sys.stderr)
		return 1
	return 0


def generate_topic():
	"""192 bits of crypto-secure entropy, URL-safe base64 (32 chars).

	UUID4 is only 122 bits and confusingly versions-stamped; secrets.token_urlsafe
	is the idiomatic stdlib answer for opaque string secrets. The token is the
	sole auth on ntfy.sh — see the safety note in the module docstring."""
	return secrets.token_urlsafe(24)


def read_message(positional: str | None) -> str:
	if positional is not None and positional != "-":
		return positional
	return sys.stdin.read()


def main(argv=None, opener=None, home=None):
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("message", nargs="?", help="body text; '-' or omitted reads stdin")
	parser.add_argument("-s", "--subject", help="notification title")
	parser.add_argument("-p", "--priority", choices=PRIORITIES, help="ntfy priority")
	parser.add_argument("-t", "--topic", help="topic name or full URL "
		"(default: $NTFY_TARGET, then ~/.config/ntfy/target)")
	parser.add_argument("--tag", action="append", default=[], help="tag, repeatable")
	parser.add_argument("--print-topic", action="store_true",
		help="print a fresh crypto-secure topic URL and the exact setup recipe, then exit")
	args = parser.parse_args(argv)

	if args.print_topic:
		url = PUBLIC_BASE + generate_topic()
		print(url)
		print(f"mkdir -p ~/.config/ntfy")
		print(f"printf '%s\\n' '{url}' > ~/.config/ntfy/target")
		print(f"chmod 600 ~/.config/ntfy/target")
		return 0

	message = read_message(args.message)
	if not message.strip():
		print("ntfy: empty message (pass one or pass to stdin)", file=sys.stderr)
		return 2
	url = target_url(resolve_target(args.topic, home=home))
	return send(url, message=message, subject=args.subject, priority=args.priority, tags=args.tag, opener=opener)


if __name__ == "__main__":
	sys.exit(main())