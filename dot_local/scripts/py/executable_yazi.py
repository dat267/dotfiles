#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import json
import subprocess
import shutil
import tempfile
import urllib.request
import urllib.parse


@click.group()
def cli():
    pass


# --- extract ---

def dest_dir(path):
    abs_path = os.path.abspath(path)
    parent = os.path.dirname(abs_path)
    base = os.path.basename(abs_path)
    name, ext1 = os.path.splitext(base)
    if ext1.lower() in {".gz", ".bz2", ".xz", ".zst", ".lzma", ".zip", ".7z", ".rar", ".tgz", ".txz", ".tbz2"}:
        name2, ext2 = os.path.splitext(name)
        if ext2.lower() == ".tar":
            name = name2
    return os.path.join(parent, name)


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
def extract(files):
    if not shutil.which("7z"):
        click.echo("Error: 7z is not installed.", err=True)
        raise SystemExit(1)

    click.echo("\n>>> Yazi Archive Extractor <<<")
    click.echo("Selected archives:")
    for f in files:
        click.echo(f"  - {os.path.basename(f)}")
    click.echo("----------------------------------------")

    for archive in files:
        dst = dest_dir(archive)
        click.echo(f"\nExtracting: {os.path.basename(archive)} -> {os.path.basename(dst)}/")
        cmd = ["7z", "x", "-y", "-mmt=on", f"-o{dst}", "--", os.path.abspath(archive)]
        click.echo(f"Command: {' '.join(cmd)}\n")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            click.echo(f"Extracted '{os.path.basename(archive)}'!")
        else:
            click.echo(f"Extraction failed for '{os.path.basename(archive)}'.", err=True)

    click.echo("----------------------------------------")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


# --- compress ---

@cli.command()
@click.argument("format", type=click.Choice(["7z", "zip"]))
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
def compress(format, files):
    if not shutil.which("7z"):
        click.echo("Error: 7z is not installed.", err=True)
        raise SystemExit(1)

    targets = [os.path.abspath(f) for f in files]
    ext = f".{format}"
    first = targets[0]

    if len(targets) == 1:
        if os.path.isdir(first):
            name = os.path.basename(first)
        else:
            name, _ = os.path.splitext(os.path.basename(first))
    else:
        name = os.path.basename(os.path.dirname(first))

    if not name:
        name = "archive"

    out = f"{name}{ext}"

    click.echo(f"\n>>> Yazi Archive Compressor <<<")
    click.echo(f"Format: {format.upper()}")
    click.echo(f"Output: {out}")
    click.echo("Files:")
    for f in targets:
        click.echo(f"  - {os.path.basename(f)}")
    click.echo("----------------------------------------")

    cmd = ["7z", "a"]
    if format == "7z":
        cmd.extend(["-t7z", "-mx=9", "-mmt=on", "-ms=on"])
    else:
        cmd.extend(["-tzip", "-mx=9", "-mm=Deflate", "-mmt=on"])
    cmd.append(out)
    cmd.extend(targets)

    click.echo(f"Running: {' '.join(cmd)}\n")
    res = subprocess.run(cmd)

    click.echo("----------------------------------------")
    if res.returncode == 0:
        click.echo(f"Created {out}!")
    else:
        click.echo("Compression failed.", err=True)

    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


# --- concat ---

@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
def concat(files):
    if not shutil.which("ffmpeg"):
        click.echo("Error: ffmpeg is not installed.", err=True)
        raise SystemExit(1)

    if len(files) < 2:
        click.echo("Error: need at least 2 files.", err=True)
        raise SystemExit(1)

    click.echo(f"\n>>> Concatenating {len(files)} files <<<")
    for f in files:
        click.echo(f"  - {os.path.basename(f)}")
    click.echo("")

    is_flac = all(f.lower().endswith(".flac") for f in files)
    ext = os.path.splitext(files[0])[1]
    parent = os.path.dirname(os.path.abspath(files[0]))
    parent_name = os.path.basename(parent)
    first_base = os.path.splitext(os.path.basename(files[0]))[0]
    generic = {"downloads", "desktop", "documents", "temp", "tmp", "videos", "music", "pictures", "home", "dat"}
    default = f"{parent_name}_combined{ext}" if parent_name.lower() not in generic else f"{first_base}_combined{ext}"

    out_name = click.prompt("Output filename", default=default)
    click.echo("")

    cmd = ["ffmpeg"]
    for f in files:
        cmd.extend(["-i", f])

    if is_flac:
        cmd += ["-filter_complex", f"concat=n={len(files)}:v=0:a=1",
                "-c:a", "flac", "-y", out_name]
    else:
        filter_str = "".join(f"[{i}:v][{i}:a]" for i in range(len(files)))
        filter_str += f" concat=n={len(files)}:v=1:a=1 [v][a]"
        cmd += ["-filter_complex", filter_str, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac", "-y", out_name]

    click.echo(f"Running: {' '.join(cmd)}\n")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        click.echo(f"Created '{out_name}'!")
    else:
        click.echo("Concat failed.", err=True)

    click.echo("")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


# --- transcode ---

@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--ext", "-e", default="mp4", help="Target extension (mp4, mp3, mkv, wav, etc.)")
def transcode(files, ext):
    if not shutil.which("ffmpeg"):
        click.echo("Error: ffmpeg is not installed.", err=True)
        raise SystemExit(1)

    ext = ext.lower()
    if not ext.startswith("."):
        ext = "." + ext

    for src in files:
        base, _ = os.path.splitext(os.path.basename(src))
        parent = os.path.dirname(os.path.abspath(src))
        out = os.path.join(parent, base + ext)
        click.echo(f"Transcoding {os.path.basename(src)} -> {os.path.basename(out)}")
        res = subprocess.run(["ffmpeg", "-i", src, "-y", out])
        if res.returncode != 0:
            click.echo(f"Failed: {os.path.basename(src)}", err=True)

    click.echo(f"\nDone — {len(files)} file(s)")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


# --- split ---

def parse_ts(s):
    parts = s.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


@cli.command()
@click.argument("filepath", type=click.Path(exists=True))
def split(filepath):
    if not shutil.which("ffmpeg"):
        click.echo("Error: ffmpeg is not installed.", err=True)
        return
    base, ext = os.path.splitext(filepath)
    parent = os.path.dirname(filepath)

    click.echo(f"File: {os.path.basename(filepath)}")
    inp = click.prompt("Timestamps (comma-separated, e.g. 0:30, 1:00)", default="")
    if not inp:
        return

    points = [parse_ts(t) for t in inp.split(",") if t.strip()]
    if not points:
        click.echo("No valid timestamps.")
        return

    points = sorted(points)
    segments = []
    prev = 0
    for i, p in enumerate(points):
        segments.append((prev, p, i + 1))
        prev = p
    segments.append((prev, None, len(points) + 1))

    click.echo(f"\nSplitting into {len(segments)} segments...")
    for start, end, idx in segments:
        label = f"part{idx:02d}"
        out = os.path.join(parent, f"{base}_{label}{ext}")
        cmd = ["ffmpeg", "-i", filepath, "-ss", str(start)]
        if end is not None:
            cmd += ["-t", str(end - start)]
        cmd += ["-c", "copy", "-y", out]
        click.echo(f"  {label}: {start}s \u2192 {end or 'end'} -> {os.path.basename(out)}")
        subprocess.run(cmd, capture_output=True)

    click.echo(f"\nDone — {len(segments)} files created.")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


# --- rename ---

@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True), required=True)
def rename(paths):
    dirs = set(os.path.dirname(p) for p in paths)
    if len(dirs) > 1:
        click.echo("Error: files must be in the same directory.", err=True)
        raise SystemExit(1)

    parent = os.path.dirname(paths[0])
    old = [os.path.basename(p) for p in paths]

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir=parent)
    tmpname = tmp.name
    for name in old:
        tmp.write(name + "\n")
    tmp.close()

    editor = os.environ.get("EDITOR", "nvim")
    subprocess.run([editor, tmpname])

    with open(tmpname) as f:
        new = [line.rstrip("\n") for line in f]
    os.remove(tmpname)

    changes = [(a, b) for a, b in zip(old, new) if a != b]
    if not changes:
        click.echo("No changes.")
        return

    for a, b in changes:
        src = os.path.join(parent, a)
        dst = os.path.join(parent, b)
        if os.path.exists(dst) and a != b:
            click.echo(f"Skip: {b} already exists.", err=True)
            continue
        os.rename(src, dst)
        click.echo(f"Renamed -> {b}")

    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


# --- translate ---

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
    click.echo(*a, err=True, **kw)


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
    click.echo(prompt, nl=False, err=True)
    return sys.stdin.readline().rstrip("\n")


@cli.command()
@click.option("--quiet", is_flag=True, help="Read text from stdin, output only translation")
@click.option("--rename", is_flag=True, help="Translate filename (stem) and rename file(s)")
@click.option("--file", is_flag=True, help="Read text from file(s), overwrite with translation")
@click.option("--langs", is_flag=True, help="List supported language codes")
@click.argument("args", nargs=-1)
def translate(quiet, rename, file, langs, args):
    """Translate text between languages using free online APIs."""
    args = list(args)

    if rename:
        if not args:
            eprint("Error: --rename requires at least one file path")
            input_flush("Press Enter to return to Yazi.")
            raise SystemExit(1)
        for p in args:
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

    if langs:
        for c in sorted(KNOWN_LANGS):
            click.echo(c)
        return

    if file:
        if not args:
            eprint("Error: --file requires at least one file path")
            input_flush("Press Enter to return to Yazi.")
            raise SystemExit(1)
        for fp in args:
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

    if not args:
        if quiet:
            text = sys.stdin.read().strip()
        else:
            eprint("=== Translator ===")
            text = click.prompt("Enter text to translate", default="")
            if text:
                t = click.prompt("Target language", default="")
                if t:
                    target = t
    else:
        text = args[0]
        target = args[1] if len(args) > 1 else "en"
        source = args[2] if len(args) > 2 else "auto"

    if not text:
        eprint("Error: text cannot be empty")
        input_flush("Press Enter to return to Yazi.")
        raise SystemExit(1)

    if not quiet:
        eprint(f"Text:     {text!r}")
        eprint(f"From:     {source}")
        eprint(f"To:       {target}")
        eprint("-" * 40)

    result = translate(text, target, source)

    if quiet:
        click.echo(result)
    else:
        eprint(f"Result:   {result}")
        eprint("-" * 40)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\nCancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
