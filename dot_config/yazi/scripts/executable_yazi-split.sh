#!/bin/sh
if [ $# -ne 1 ]; then
	echo "Split only works on a single file."
	read -p "Press Enter..."
	exit 1
fi

f="$1"
base="${f%.*}"
ext="${f##*.}"
dir="$(dirname "$f")"

printf "Timestamps (comma-separated, e.g. 0:30, 1:00): "
read -r ts
[ -z "$ts" ] && exit

IFS=','
idx=1
prev=0
for t in $ts; do
	t=$(echo "$t" | xargs)
	[ -z "$t" ] && continue
	label=$(printf "part%02d" "$idx")
	ffmpeg -i "$f" -ss "$prev" -to "$t" -c copy -y "$dir/${base}_$label.$ext"
	prev="$t"
	idx=$((idx+1))
done
label=$(printf "part%02d" "$idx")
ffmpeg -i "$f" -ss "$prev" -c copy -y "$dir/${base}_$label.$ext"

echo
read -p "Press Enter to return to Yazi."
