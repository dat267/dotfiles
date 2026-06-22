#!/bin/sh

file="$1"
width="$2"
height="$3"

[ -r "$file" ] || exit 0
mime=$(file -Lb --mime-type "$file")

case "$mime" in
    inode/directory)
        command -v tree >/dev/null && tree -C -L 2 --dirsfirst "$file" | head -n "$height" || ls -lh --color=always "$file" | head -n "$height"
        ;;
    application/zip)
        command -v zipinfo >/dev/null && zipinfo "$file" | head -n "$height" || unzip -l "$file" | head -n "$height"
        ;;
    application/x-tar|application/x-gzip|application/x-bzip2|application/x-xz|application/x-compressed-tar)
        tar -tvf "$file" 2>/dev/null | head -n "$height"
        ;;
    application/x-7z-compressed|application/x-rar)
        command -v 7z >/dev/null && 7z l "$file" 2>/dev/null | head -n "$height" || echo "Archive: $(basename "$file")"
        ;;
    text/*|application/json|*javascript|*xml|*sh|text/html)
        command -v bat >/dev/null && bat --color=always --style=changes,numbers --terminal-width="$width" "$file" 2>/dev/null | head -n "$height" || head -n "$height" "$file"
        ;;
    *)
        stat "$file" 2>/dev/null || file "$file"
        ;;
esac
