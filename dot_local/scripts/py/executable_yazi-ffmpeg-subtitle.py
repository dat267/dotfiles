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
    tmp = filepath + ".tmp"
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
    parser = argparse.ArgumentParser(description="Reorder subtitle tracks in a media file.")
    parser.add_argument("file", help="Media file to process (single file)")
    args = parser.parse_args()

    filepath = os.path.abspath(args.file)
    if not os.path.isfile(filepath):
        print_flush(f"Error: File not found: {filepath}")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    subs = get_subtitle_streams(filepath)
    if not subs:
        print_flush(f"No subtitle streams found in {os.path.basename(filepath)}.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    print_flush(f"\nFile: {os.path.basename(filepath)}")
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

    output = promote_subtitle(filepath, target)
    if output:
        print_flush(f"\nSubtitles reordered: {os.path.basename(filepath)}")
    else:
        print_flush("Failed to reorder subtitles.")

    input_flush("Press Enter to return to Yazi.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nCancelled.")
        sys.exit(0)
