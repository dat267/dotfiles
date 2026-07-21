#!/usr/bin/env python3
"""
Translate text between languages using free online APIs.

Usage:
  %(name)s                              Interactive mode
  %(name)s --quiet                     Read text from stdin, output only translation
   %(name)s --quiet --file <path>...    Read text from file(s), overwrite with translation
   %(name)s --rename <path>...          Translate filename (stem) and rename file(s)
  %(name)s <text> [target] [source]     Translate <text> to target language (default: en)
  %(name)s --langs                     List supported language codes
  %(name)s --help                      Show this help
"""
import sys
import json
import os
import urllib.request
import urllib.parse

LINGVA = "https://lingva.ml/api/v1"
MYMEMORY = "https://api.mymemory.translated.net/get"

KNOWN_LANGS = {
    "af", "sq", "am", "ar", "hy", "az", "eu", "be", "bn", "bs", "bg",
    "ca", "ceb", "zh", "zh-CN", "zh-TW", "co", "hr", "cs", "da",
    "nl", "en", "eo", "et", "fi", "fr", "fy", "gl", "ka", "de",
    "el", "gu", "ht", "ha", "haw", "he", "iw", "hi", "hmn", "hu",
    "is", "ig", "id", "ga", "it", "ja", "jv", "kn", "kk", "km",
    "rw", "ko", "ku", "ky", "lo", "la", "lv", "lt", "lb", "mk",
    "mg", "ms", "ml", "mt", "mi", "mr", "mn", "my", "ne", "no",
    "ny", "or", "ps", "fa", "pl", "pt", "pa", "ro", "ru", "sm",
    "gd", "sr", "st", "sn", "sd", "si", "sk", "sl", "so", "es",
    "su", "sw", "sv", "tl", "tg", "ta", "tt", "te", "th", "tr",
    "tk", "uk", "ur", "ug", "uz", "vi", "cy", "xh", "yi", "yo", "zu",
}

_UA = "Mozilla/5.0 (X11; Linux x86_64)"


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


def _guess_lang(text):
    """Crude script-based language guess for fallback scenarios."""
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff")
    if cjk > 5:
        return "ja"
    kr = sum(1 for c in text if "\uac00" <= c <= "\ud7af")
    if kr > 5:
        return "ko"
    ru = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    if ru > 5:
        return "ru"
    return "en"


def _detect_encoding(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "shift_jis", "cp932", "euc-jp", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _json_get(url, *, data=None):
    h = {"User-Agent": _UA}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def translate_lingva(text, target, source="auto"):
    data = _json_get(f"{LINGVA}/{source}/{target}/{urllib.parse.quote(text, safe='')}")
    t = data.get("translation")
    if not t:
        raise ValueError(f"Lingva: {data}")
    return t


def translate_mymemory(text, target, source):
    url = f"{MYMEMORY}?{urllib.parse.urlencode({'q': text, 'langpair': f'{source}|{target}'})}"
    data = _json_get(url)
    t = data.get("responseData", {}).get("translatedText")
    if not t:
        raise ValueError(f"MyMemory: {data.get('responseDetails', 'empty')}")
    return t


# Lingva uses GET with text in the URL path. URL-encoded CJK text
# expands ~3x (each UTF-8 byte → %XX), so cap at 200 raw chars to stay
# under common 2000-char URI limits. Non-CJK text is fine since ASCII
# is not percent-encoded by urllib.
_MAX_CHUNK = 200
_UA_LIMIT = 2000


def _url_size(text):
    """Rough URL path size for Lingva API with this text.
    Must match translate_lingva's encoding (safe='') to be accurate."""
    encoded = urllib.parse.quote(text, safe="")
    return len(f"{LINGVA}/auto/en/{encoded}")


def _translate_one(text, target, source):
    providers = [translate_lingva]
    if source != "auto":
        providers.append(translate_mymemory)
    else:
        # Lingva may fail on text containing '://' (midware decodes %2F → /
        # before the app sees it, breaking the route). Fall back to MyMemory
        # which uses a query param, avoiding the issue entirely. Guess the
        # source language from script ranges.
        providers.append(lambda t, tg, src: translate_mymemory(t, tg, _guess_lang(t)))
    for fn in providers:
        try:
            return fn(text, target, source)
        except Exception as e:
            eprint(f"{fn.__name__}: {e}")
            continue
    raise RuntimeError("all providers failed")


def translate(text, target, source="auto"):
    if _url_size(text) < _UA_LIMIT:
        return _translate_one(text, target, source)

    lines = text.split("\n")
    result = []
    buf = ""
    for line in lines:
        candidate = (buf + "\n" + line).strip() if buf else line
        if _url_size(candidate) < _UA_LIMIT:
            buf = candidate
        else:
            if buf:
                result.append(_translate_one(buf, target, source))
            buf = line
    if buf:
        result.append(_translate_one(buf, target, source))
    return "\n".join(result)


def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip("
")


def main():
    args = sys.argv[1:]
    quiet = False

    if args and args[0] == "--quiet":
        quiet = True
        args = args[1:]

    if args and args[0] == "--rename":
        if len(args) < 2:
            eprint("Error: --rename requires at least one file path")
            input_flush("Press Enter to return to Yazi.")
            sys.exit(1)
        for p in args[1:]:
            if len(p) >= 2 and p[0] == p[-1] and p[0] in "'\"":
                p = p[1:-1]
            name = os.path.basename(p)
            dot = name.rfind(".")
            if dot > 0 and not name.startswith("."):
                stem = name[:dot]
                ext = name[dot:]
            else:
                stem = name
                ext = ""
            translated = translate(stem, "en", "auto")
            if translated != stem:
                new = os.path.join(os.path.dirname(p), translated + ext)
                os.rename(p, new)
                eprint(f"Renamed -> {os.path.basename(new)}")
        input("Press Enter to return to Yazi.")
        return

    if args and args[0] == "--langs":
        for c in sorted(KNOWN_LANGS):
            print(c)
        return

    if args and args[0] in ("--help", "-h"):
        print(__doc__ % {"name": "translate"})
        return

    if args and args[0] == "--file":
        if len(args) < 2:
            eprint("Error: --file requires at least one file path")
            input_flush("Press Enter to return to Yazi.")
            sys.exit(1)
        for fp in args[1:]:
            if len(fp) >= 2 and fp[0] == fp[-1] and fp[0] in "'\"":
                fp = fp[1:-1]
            enc = _detect_encoding(fp)
            with open(fp, encoding=enc) as f:
                text = f.read().strip()
            if not text:
                eprint(f"Error: {fp} is empty")
                continue
            result = translate(text, "en", "auto")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(result + "\n")
            eprint(f"Translated -> {fp}")
        input("Press Enter to return to Yazi.")
        return

    if len(args) == 0:
        if quiet:
            text = sys.stdin.read().strip()
        else:
            eprint("=== Translator ===")
            text = input("Enter text to translate: ").strip()
            if text:
                t = input("Target language (default: en): ").strip()
                if t:
                    target = t
    else:
        text = args[0]
        target = args[1] if len(args) > 1 else "en"
        source = args[2] if len(args) > 2 else "auto"

    if not text:
        eprint("Error: text cannot be empty")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    if not quiet:
        eprint(f"Text:     {text!r}")
        eprint(f"From:     {source}")
        eprint(f"To:       {target}")
        eprint("-" * 40)

    result = translate(text, target, source)

    if quiet:
        print(result)
    else:
        eprint(f"Result:   {result}")
        eprint("-" * 40)


if __name__ == "__main__":
    main()
