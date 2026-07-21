#!/bin/sh
printf "Target extension (e.g. mp4, mp3, mkv, wav) [mp4]: "
read -r ext
[ -z "$ext" ] && ext="mp4"

for f in "$@"; do
	base="${f%.*}"
	out="$base.$ext"
	ffmpeg -i "$f" -y "$out"
done
echo
read -p "Press Enter to return to Yazi."
