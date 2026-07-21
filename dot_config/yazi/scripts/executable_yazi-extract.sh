#!/bin/sh
for f in "$@"; do
	d="${f%.*}"
	mkdir -p "$d"
	7z x -y "$f" -o"$d"
done
echo
read -p "Press Enter to return to Yazi."
