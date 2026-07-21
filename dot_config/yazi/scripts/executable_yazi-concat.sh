#!/bin/sh
if [ $# -lt 2 ]; then
	echo "Need at least 2 files."
	read -p "Press Enter..."
	exit 1
fi

printf "Output filename: "
read -r out
[ -z "$out" ] && out="concatenated.${1##*.}"

flac=1
for f in "$@"; do
	case "$f" in *.flac|*.FLAC) ;; *) flac=0; break ;; esac
done

n=$#
cmd="ffmpeg"
i=0
for f in "$@"; do
	cmd="$cmd -i \"$f\""
	i=$((i+1))
done

if [ "$flac" = 1 ]; then
	cmd="$cmd -filter_complex \"concat=n=$n:v=0:a=1\" -c:a flac -y \"$out\""
else
	filter=""
	i=0
	while [ $i -lt $n ]; do
		filter="${filter}[$i:v][$i:a]"
		i=$((i+1))
	done
	filter="${filter}concat=n=$n:v=1:a=1[v][a]"
	cmd="$cmd -filter_complex \"$filter\" -map \"[v]\" -map \"[a]\" -c:v libx264 -c:a aac -y \"$out\""
fi

eval $cmd
echo
read -p "Press Enter to return to Yazi."
