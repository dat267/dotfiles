#!/usr/bin/env python3
"""translate-en.py — translate text files to English via chat.deepseek.com.

Speaks DeepSeek's web chat protocol directly (reverse-engineered from the
browser client):
    1. POST /api/v0/chat_session/create        -> session id
    2. POST /api/v0/chat/create_pow_challenge  -> PoW challenge
    3. solve the challenge with DeepSeek's own WASM (via `node`)
    4. POST /api/v0/chat/completion  (SSE)     -> translated text

nothink / nosearch mode is hardcoded: `thinking_enabled: false`,
`search_enabled: false`, `model_type: "default"` (Instant).

Authentication (never commit these — secret-scan doctrine):
- DEEPSEEK_TOKEN env var, or "token" in ~/.config/deepseek/chat-token.json
- DEEPSEEK_DS_SESSION_ID env var, or "ds_session_id" in the same 0600 file

To grab them from a logged-in browser: DevTools -> Application ->
Local Storage -> chat.deepseek.com -> `userToken` (the token), and
Cookies -> `ds_session_id`. Save to the 0600 file or export for the
command only.

Requires `node` (WebAssembly PoW solver) and reachability of
chat.deepseek.com. Personal use only; the endpoint may change or rate
limit without notice.

Usage:
    translate-en.py file1.md file2.txt
    translate-en.py -r docs/ --out-dir ./en
    translate-en.py --in-place README.md
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://chat.deepseek.com"
SESSION_CREATE = "/api/v0/chat_session/create"
POW_CHALLENGE = "/api/v0/chat/create_pow_challenge"
COMPLETION = "/api/v0/chat/completion"

HERE = Path(__file__).resolve().parent
WASM = HERE / "_vendor" / "deepseek" / "sha3_wasm_bg.wasm"
TOKEN_FILE = Path.home() / ".config" / "deepseek" / "chat-token.json"

MODEL_TYPE = "default"          # "default" = Instant (no think); "expert" = stronger
THINKING_ENABLED = False        # nothink
SEARCH_ENABLED = False          # nosearch
DEFAULT_CHUNK = 2500
MAX_RETRIES = 3

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def eprint(msg):
    print(msg, file=sys.stderr)


class DeepSeekError(RuntimeError):
    pass


def load_auth() -> tuple[str, str]:
    """Return (token, ds_session_id) from env or the 0600 local file."""
    token = os.environ.get("DEEPSEEK_TOKEN", "").strip()
    sid = os.environ.get("DEEPSEEK_DS_SESSION_ID", "").strip()
    if not token and TOKEN_FILE.is_file():
        try:
            data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        token = data.get("token", "").strip()
        sid = sid or data.get("ds_session_id", "").strip()
    if not token:
        raise DeepSeekError(
            "No DeepSeek token found. Set DEEPSEEK_TOKEN (optionally "
            f"DEEPSEEK_DS_SESSION_ID) or create {TOKEN_FILE} with "
            '{"token": "...", "ds_session_id": "..."} (chmod 600). '
            "Values come from your browser: DevTools -> Application -> "
            "Local Storage -> chat.deepseek.com -> userToken; Cookies -> "
            "ds_session_id."
        )
    return token, sid


def headers(token, sid, extra=None):
    h = {
        "authorization": f"Bearer {token}",
        "accept": "*/*",
        "content-type": "application/json",
        "user-agent": UA,
        "origin": BASE,
        "referer": f"{BASE}/",
        "x-app-version": "2.0.0",
        "x-client-version": "2.0.0",
        "x-client-platform": "web",
        "x-client-locale": "en_US",
        "x-client-bundle-id": "com.deepseek.chat",
    }
    if sid:
        h["cookie"] = f"ds_session_id={sid}"
    if extra:
        h.update(extra)
    return h


def biz(resp_json: dict) -> dict:
    if resp_json.get("code") != 0:
        raise DeepSeekError(f"DeepSeek API error: {resp_json.get('msg') or resp_json}")
    bd = resp_json.get("data", {}).get("biz_data")
    if bd is None:
        raise DeepSeekError(f"Unexpected response shape: {resp_json}")
    return bd


def http_json(token, sid, path, payload) -> dict:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers=headers(token, sid), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code in (401, 403):
            raise DeepSeekError(
                f"Authentication failed ({e.code}): token expired or rejected. "
                "Re-copy the userToken from your browser.") from e
        raise DeepSeekError(f"HTTP {e.code}: {body[:300]}") from e
    except urllib.error.URLError as e:
        raise DeepSeekError(f"Network error: {e.reason}") from e


POW_JS = r'''
import { readFileSync } from "node:fs";
const [wasmPath, challenge, prefix, difficulty] = process.argv.slice(1);
const { instance } = await WebAssembly.instantiate(readFileSync(wasmPath), {});
const e = instance.exports;
const enc = new TextEncoder();
const writeStr = (ptr, s) => new Uint8Array(e.memory.buffer, ptr).set(enc.encode(s));
const rp = e.__wbindgen_add_to_stack_pointer(-16);
try {
  const cp = e.__wbindgen_export_0(challenge.length, 1);
  writeStr(cp, challenge);
  const pp = e.__wbindgen_export_0(prefix.length, 1);
  writeStr(pp, prefix);
  e.wasm_solve(rp, cp, challenge.length, pp, prefix.length, Number(difficulty));
  const dv = new DataView(e.memory.buffer);
  if (dv.getInt32(rp, true) === 0) process.exit(2);
  process.stdout.write(String(Math.trunc(dv.getFloat64(rp + 8, true))));
} finally {
  e.__wbindgen_add_to_stack_pointer(16);
}
'''


def pow_header(token, sid, node_bin="node") -> str:
    """Solve the PoW challenge; return the x-ds-pow-response header value."""
    challenge = biz(http_json(token, sid, POW_CHALLENGE,
                             {"target_path": COMPLETION}))["challenge"]
    prefix = f"{challenge['salt']}_{challenge['expire_at']}_"
    proc = subprocess.run(
        [node_bin, "--input-type=module", "-e", POW_JS, "--",
         str(WASM), challenge["challenge"], prefix, str(challenge["difficulty"])],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise DeepSeekError(
            "PoW solve failed: "
            + (proc.stderr.strip() or f"node exited {proc.returncode}; is node installed?"))
    payload = {
        "algorithm": challenge["algorithm"],
        "challenge": challenge["challenge"],
        "salt": challenge["salt"],
        "answer": int(proc.stdout.strip()),
        "signature": challenge["signature"],
        "target_path": challenge["target_path"],
    }
    return base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("utf-8")


def create_session(token, sid) -> str:
    return biz(http_json(token, sid, SESSION_CREATE, {}))["chat_session"]["id"]


def parse_sse(lines) -> tuple[str, int | None]:
    """DeepSeek streams JSON-patch frames over SSE; only the 'response'
    fragment content is translation text. Returns (text, message_id?)."""
    parts: list[str] = []
    active: str | None = None
    message_id: int | None = None
    for raw in lines:
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        p, v = obj.get("p"), obj.get("v")
        if isinstance(v, dict):
            # Initial snapshot: v is the whole response object.
            mid = v.get("message_id")
            if mid is None:
                msg = v.get("message") or {}
                mid = msg.get("id")
            if mid is not None:
                try:
                    message_id = int(mid)
                except (TypeError, ValueError):
                    pass
            for frag in v.get("fragments") or []:
                if frag.get("type") == "response":
                    parts.append(frag.get("content", ""))
            active = None
        elif isinstance(v, str):
            if p:
                active = p
            if active and active.startswith("response/fragments/-1/content"):
                parts.append(v)
    return "".join(parts), message_id


def complete(token, sid, session_id, parent_message_id, prompt, node_bin,
             first_turn: bool) -> tuple[str, int | None]:
    body = {
        "chat_session_id": session_id,
        "parent_message_id": parent_message_id,
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": THINKING_ENABLED,
        "search_enabled": SEARCH_ENABLED,
        "action": None,
        "preempt": False,
    }
    if first_turn:
        body["model_type"] = MODEL_TYPE
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                BASE + COMPLETION,
                data=json.dumps(body).encode("utf-8"),
                headers=headers(token, sid,
                                {"x-ds-pow-response": pow_header(token, sid, node_bin)}),
                method="POST")
            with urllib.request.urlopen(req, timeout=300) as r:
                text, mid = parse_sse(r)
            if not text.strip():
                raise DeepSeekError("empty completion; retrying")
            return text, mid
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise DeepSeekError(
                    f"Authentication failed ({e.code}): token expired or rejected. "
                    "Re-copy the userToken from your browser.") from e
            if e.code in (429, 500, 502, 503) and attempt < MAX_RETRIES - 1:
                last_err = DeepSeekError(f"HTTP {e.code}")
            else:
                raise DeepSeekError(
                    f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
        except urllib.error.URLError as e:
            last_err = DeepSeekError(f"network: {e.reason}")
        except DeepSeekError as e:
            last_err = e
        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
    raise DeepSeekError(f"completion failed after {MAX_RETRIES} attempts: {last_err}")


INSTRUCTION = (
    "You are a translator. Translate the provided text into natural, fluent "
    "English. Keep markdown, code blocks, inline code, URLs, and identifiers "
    "unchanged; translate only human prose. Output ONLY the translation, "
    "no commentary."
)


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split into chunks on paragraph boundaries, hard-splitting monsters."""
    text = text.replace("\r\n", "\n")
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for block in text.split("\n\n"):
        if cur and cur_len + len(block) + 2 > max_chars:
            chunks.append("\n\n".join(cur))
            cur, cur_len = [], 0
        while len(block) > max_chars:
            cut = block[:max_chars]
            chunks.append(cut)
            block = block[max_chars:]
        if block:
            cur.append(block)
            cur_len += len(block) + 2
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def translate_file(token, sid, node_bin, src: Path, out: Path,
                   max_chars: int, quiet: bool) -> int:
    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise DeepSeekError(f"{src}: not valid UTF-8 text; skipping")
    if not text.strip():
        eprint(f"{src}: empty; skipping")
        return 0
    if "\x00" in text[:8192]:
        raise DeepSeekError(f"{src}: looks binary; skipping")
    chunks = chunk_text(text, max_chars)
    if not quiet:
        eprint(f"{src}: {len(chunks)} chunk(s)")
    session_id = create_session(token, sid)
    parent = None
    first = True
    translated: list[str] = []
    for chunk in chunks:
        prompt = INSTRUCTION + "\n\n" + chunk if first else (
            "Continue the translation. Translate the provided text into "
            "natural, fluent English.\n\n" + chunk)
        out_text, mid = complete(token, sid, session_id, parent, prompt,
                                 node_bin, first_turn=first)
        translated.append(out_text.rstrip() + "\n")
        parent = mid
        first = False
        if mid is None:
            # Could not link turns; restart with a fresh session next round.
            session_id = create_session(token, sid)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(translated), encoding="utf-8")
    return len(chunks)


def gather(paths, recursive) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            if not recursive:
                raise SystemExit(f"{p}: is a directory (use -r)")
            files.extend(x for x in sorted(p.rglob("*")) if x.is_file())
        elif p.is_file():
            files.append(p)
        elif p.exists():
            raise SystemExit(f"{p}: not a regular file")
        else:
            raise SystemExit(f"{p}: no such file")
    return files


def out_path(src: Path, out_dir, in_place) -> Path:
    if in_place:
        return src
    name = src.stem + "-en" + src.suffix
    return (out_dir / name) if out_dir else src.with_name(name)


def main():
    ap = argparse.ArgumentParser(
        prog="translate-en",
        description="Translate text files to English via chat.deepseek.com "
                    "(nothink/nosearch Instant mode).")
    ap.add_argument("paths", nargs="+", help="files (or dirs with -r)")
    ap.add_argument("-r", "--recursive", action="store_true",
                    help="recurse into directories")
    ap.add_argument("--out-dir", default=None,
                    help="write outputs into this directory")
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite the input file")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_CHUNK,
                    help="max characters per API chunk (default %(default)s)")
    ap.add_argument("--node", default="node",
                    help="node executable for the PoW solver (default %(default)s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan without calling the API")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="only print output paths")
    args = ap.parse_args()

    files = gather(args.paths, args.recursive)
    if args.dry_run:
        for f in files:
            try:
                text = f.read_text(encoding="utf-8")
                n = len(chunk_text(text, args.max_chars)) if text.strip() else 0
            except (UnicodeDecodeError, OSError) as e:
                eprint(f"{f}: {e}")
                continue
            eprint(f"{f} -> {out_path(f, args.out_dir, args.in_place)}"
                   + (f" ({n} chunk(s))" if n else " (empty)"))
        return

    token, sid = load_auth()
    errors = 0
    for f in files:
        out = out_path(f, args.out_dir, args.in_place)
        if out.resolve() == f.resolve():
            eprint(f"{f}: would overwrite in place (use --in-place)")
            continue
        try:
            translate_file(token, sid, args.node, f, out, args.max_chars, args.quiet)
            print(out)          # pipeline-friendly: output file paths on stdout
        except DeepSeekError as e:
            eprint(f"{f}: ERROR: {e}")
            errors += 1
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())