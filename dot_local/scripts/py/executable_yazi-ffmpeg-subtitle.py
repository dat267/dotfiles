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

    # Collect all unique track titles across all files
    all_titles = {}
    title_at_index = {}  # title -> {index -> [filenames]}
    for f in files:
        subs = get_subtitle_streams(f)
        for i, s in enumerate(subs):
            t = s["title"] or f"(untitled {s['lang']})"
            if t not in all_titles:
                all_titles[t] = {"lang": s["lang"], "codec": s["codec"]}
            title_at_index.setdefault(t, {}).setdefault(i, []).append(os.path.basename(f))

    sorted_titles = sorted(all_titles.keys())
    if not sorted_titles:
        print_flush("No subtitle tracks found.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    print_flush(f"\nAll unique subtitle tracks across {len(files)} file(s):")
    for i, t in enumerate(sorted_titles):
        info = all_titles[t]
        print_flush(f"  [{i}] {t} ({info['lang']}, {info['codec']})")
        for idx in sorted(title_at_index[t]):
            for name in title_at_index[t][idx]:
                print_flush(f"      @{idx}: {name}")

    choice = input_flush(f"\nTrack to promote to position 1 (0-{len(sorted_titles)-1}, Enter=skip): ").strip()
    if choice == "":
        print_flush("Cancelled.")
        sys.exit(0)
    try:
        target_idx = int(choice)
    except ValueError:
        print_flush("Invalid choice.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)
    if target_idx < 0 or target_idx >= len(sorted_titles):
        print_flush("Out of range.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(0)

    target_title = sorted_titles[target_idx]
    ok = fail = skip = 0

    for f in files:
        subs = get_subtitle_streams(f)
        # Find target track's local subtitle index by title
        target_sub_idx = None
        for i, s in enumerate(subs):
            t = s["title"] or f"(untitled {s['lang']})"
            if t == target_title:
                target_sub_idx = i
                break
        if target_sub_idx is None or len(subs) < 2:
            skip += 1
            continue
        if target_sub_idx == 0:
            skip += 1
            continue
        if promote_subtitle(f, target_sub_idx):
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
