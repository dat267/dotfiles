#!/usr/bin/env python3
"""
Translate text between languages using free online APIs.

Usage:
  %(name)s                              Interactive mode
  %(name)s --quiet                     Read text from stdin, output only translation
  %(name)s --quiet --file <path>       Read text from file, overwrite with translation
  %(name)s <text> [target] [source]     Translate <text> to target language (default: en)
  %(name)s --langs                     List supported language codes
  %(name)s --help                      Show this help
"""
import sys
import json
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


def _json_get(url, *, data=None):
    h = {"User-Agent": _UA}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def translate_lingva(text, target, source="auto"):
    data = _json_get(f"{LINGVA}/{source}/{target}/{urllib.parse.quote(text)}")
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


def translate(text, target, source="auto"):
    if source == "auto":
        # Lingva handles auto-detection internally
        try:
            return translate_lingva(text, target, "auto")
        except Exception as e:
            eprint(f"Lingva: {e}")
    else:
        # Specified source — try Lingva first, then MyMemory
        try:
            return translate_lingva(text, target, source)
        except Exception as e:
            eprint(f"Lingva: {e}")
            try:
                return translate_mymemory(text, target, source)
            except Exception as e2:
                eprint(f"MyMemory: {e2}")

    eprint("Translation failed.")
    sys.exit(2)


def main():
    args = sys.argv[1:]
    quiet = False

    if args and args[0] == "--quiet":
        quiet = True
        args = args[1:]

    if args and args[0] == "--langs":
        for c in sorted(KNOWN_LANGS):
            print(c)
        return

    if args and args[0] in ("--help", "-h"):
        print(__doc__ % {"name": "translate"})
        return

    filepath = None
    text = ""
    target = "en"
    source = "auto"

    if args and args[0] == "--file":
        if len(args) < 2:
            eprint("Error: --file requires a path argument")
            sys.exit(1)
        filepath = args[1]
        args = args[2:]

    if filepath:
        with open(filepath) as f:
            text = f.read().strip()
        if not text:
            eprint(f"Error: {filepath} is empty")
            sys.exit(1)
    elif len(args) == 0:
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
        sys.exit(1)

    if not quiet and not filepath:
        eprint(f"Text:     {text!r}")
        eprint(f"From:     {source}")
        eprint(f"To:       {target}")
        eprint("-" * 40)

    result = translate(text, target, source)

    if filepath:
        with open(filepath, "w") as f:
            f.write(result + "\n")
        eprint(f"Translated -> {filepath}")
    elif quiet:
        print(result)
    else:
        eprint(f"Result:   {result}")
        eprint("-" * 40)


if __name__ == "__main__":
    main()
