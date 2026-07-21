#!/bin/sh

file="$1"
width="$2"
height="$3"

[ -r "$file" ] || exit 0

if [ -d "$file" ]; then
    ls -lh --color=always "$file" | head -n "$height"
    exit
fi

ext="${file##*.}"
lowext="$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"

case "$lowext" in
    7z|zip|rar|tar|gz|bz2|xz|zst)
        command -v 7z >/dev/null && 7z l "$file" 2>/dev/null | head -n "$height" || echo "Archive: $(basename "$file")"
        ;;
    *)
        head -n "$height" "$file" 2>/dev/null || stat "$file" 2>/dev/null
        ;;
esac
