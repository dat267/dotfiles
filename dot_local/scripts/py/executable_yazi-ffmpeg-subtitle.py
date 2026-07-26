#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys


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
        subprocess.run(cmd, check=True)
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
    parser.add_argument("files", nargs="+", help="Media files to process")
    args = parser.parse_args()

    files = [os.path.abspath(f) for f in args.files if os.path.isfile(f)]
    if not files:
        print_flush("Error: No valid files provided.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    # Show first file's subtitle tracks as reference
    subs = get_subtitle_streams(files[0])
    if not subs:
        print_flush(f"No subtitle streams found in {os.path.basename(files[0])}.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)
    if len(subs) < 2:
        print_flush(f"Only 1 subtitle track in {os.path.basename(files[0])} — nothing to reorder.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    print_flush(f"\nReference: {os.path.basename(files[0])}")
    print_flush("Subtitle tracks:")
    for i, s in enumerate(subs):
        title = f" - {s['title']}" if s["title"] else ""
        print_flush(f"  [{i}]  index={s['index']}  lang={s['lang']}  codec={s['codec']}{title}")

    choice = input_flush(f"\nTrack to promote to position 1 (0-{len(subs)-1}): ").strip()
    try:
        target = int(choice)
    except ValueError:
        print_flush(f"Invalid choice: {choice}")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    if target < 0 or target >= len(subs):
        print_flush(f"Track {target} is out of range.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    if target == 0:
        print_flush("Track 0 is already first. Nothing to do.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    ok = 0
    fail = 0
    for f in files:
        subs = get_subtitle_streams(f)
        if len(subs) < 2:
            print_flush(f"\n  {os.path.basename(f)}: {len(subs)} track(s), skipping")
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
