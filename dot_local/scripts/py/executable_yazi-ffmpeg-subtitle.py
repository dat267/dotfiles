#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()


def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip("\r\n")


def get_subtitle_streams(filepath):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
    except Exception as e:
        print_flush(f"Error reading streams: {e}")
        return []

    subs = []
    for s in data.get("streams", []):
        if s.get("codec_type") != "subtitle":
            continue
        idx = s.get("index")
        codec = s.get("codec_name", "?")
        lang = s.get("tags", {}).get("language", "?")
        title = s.get("tags", {}).get("title", "")
        # ffprobe stream index may be global, find the subtitle-local index
        subs.append({"index": idx, "codec": codec, "lang": lang, "title": title})
    return subs


def get_subtitle_count(filepath):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
    except Exception:
        return 0
    return len([s for s in data.get("streams", []) if s.get("codec_type") == "subtitle"])


def promote_subtitle(filepath, target_sub_idx):
    sub_count = get_subtitle_count(filepath)
    if sub_count < 2:
        print_flush("Need at least 2 subtitle tracks to reorder.")
        return False

    import tempfile
    ext = os.path.splitext(filepath)[1] or ".mkv"
    tmp = filepath + ".reorder" + ext
    cmd = ["ffmpeg", "-y", "-i", filepath]
    cmd.extend(["-map", "0:v"])
    cmd.extend(["-map", "0:a"])
    cmd.extend(["-map", f"0:s:{target_sub_idx}"])
    for i in range(sub_count):
        if i != target_sub_idx:
            cmd.extend(["-map", f"0:s:{i}"])
    cmd.extend(["-c", "copy"])
    cmd.extend(["-disposition:s:0", "default"])
    cmd.append(tmp)

    print_flush(f"\nRunning: {' '.join(cmd)}\n")
    try:
        subprocess.run(cmd, check=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print_flush(f"Error: ffmpeg failed with exit code {e.returncode}")
        if os.path.exists(tmp):
            os.remove(tmp)
        return False

    os.replace(tmp, filepath)
    return True


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print_flush("Error: ffmpeg/ffprobe is not installed or not in PATH.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="Reorder subtitle tracks in media files.")
    parser.add_argument("files", nargs="*", help="Media files to process")
    parser.add_argument("--dir", metavar="DIR", help="Process all video files in a directory")
    args = parser.parse_args()

    files = []
    if args.files:
        files = [os.path.abspath(f) for f in args.files if os.path.isfile(f)]
    elif args.dir:
        d = os.path.abspath(args.dir)
        if os.path.isdir(d):
            video_exts = {".mkv", ".mp4", ".avi", ".mov", ".m4v"}
            files = sorted(
                os.path.join(d, f) for f in os.listdir(d)
                if os.path.splitext(f)[1].lower() in video_exts
            )
    if not files:
        print_flush("Error: No valid files provided.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    # Scan all files
    file_subs = {}
    counts = {}
    for f in files:
        subs = get_subtitle_streams(f)
        file_subs[f] = subs
        n = len(subs)
        counts.setdefault(n, []).append(f)

    if not any(file_subs.values()):
        print_flush("No subtitle streams found in any selected file.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    # Show summary
    print_flush(f"\nSelected {len(files)} file(s):")
    for n, flist in sorted(counts.items()):
        print_flush(f"  {len(flist)} file(s) with {n} subtitle track(s)")
    print_flush("")

    # Show first file's tracks as reference
    ref_file = files[0]
    ref_subs = file_subs[ref_file]
    print_flush(f"Reference ({os.path.basename(ref_file)}):")
    for i, s in enumerate(ref_subs):
        title = f" - {s['title']}" if s["title"] else ""
        print_flush(f"  [{i}]  lang={s['lang']}  codec={s['codec']}{title}")

    if len(counts) > 1:
        odd = [os.path.basename(f) for n, flist in sorted(counts.items())
               if n != len(ref_subs) for f in flist]
        print_flush(f"\nWarning: {len(odd)} file(s) have different subtitle track counts:")
        for name in odd[:10]:
            print_flush(f"  - {name}")
        if len(odd) > 10:
            print_flush(f"  ... and {len(odd) - 10} more")

    if len(ref_subs) < 2:
        print_flush(f"\nOnly {len(ref_subs)} subtitle track(s) in reference file — nothing to reorder.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    # Cache: reuse previous choice within 30 seconds (for Yazi per-file invocation)
    cache = os.path.join(tempfile.gettempdir(), "yazi-subtitle-reorder")
    choice = None
    if os.path.isfile(cache) and time.time() - os.path.getmtime(cache) < 30:
        with open(cache) as f:
            choice = f.read().strip()

    if choice is not None:
        try:
            target = int(choice)
        except ValueError:
            choice = None

    if choice is None:
        raw = input_flush(f"\nTrack to promote to position 1 (0-{len(ref_subs)-1}): ").strip()
        if raw == "":
            print_flush("Cancelled.")
            sys.exit(0)
        try:
            target = int(raw)
        except ValueError:
            print_flush(f"Invalid choice.")
            input_flush("Press Enter to return to Yazi.")
            sys.exit(0)
        with open(cache, "w") as f:
            f.write(str(target))
    else:
        target = int(choice)
        print_flush(f"Using cached choice: track {target}")
    if target < 0 or target >= len(ref_subs):
        print_flush(f"Track {target} is out of range.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)
    if target == 0:
        print_flush("Track 0 is already first. Nothing to do.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    ok = 0
    fail = 0
    skip = 0
    for f in files:
        subs = file_subs[f]
        if len(subs) < 2 or target >= len(subs):
            print_flush(f"  {os.path.basename(f)}: {len(subs)} track(s), skipping")
            skip += 1
            continue
        if promote_subtitle(f, target):
            print_flush(f"  {os.path.basename(f)}: OK")
            ok += 1
        else:
            print_flush(f"  {os.path.basename(f)}: FAILED")
            fail += 1

    input_flush("Press Enter to return to Yazi.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nCancelled.")
        sys.exit(0)
