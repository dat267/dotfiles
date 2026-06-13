#!/bin/sh
# lf previewer script

file="$1"
width="$2"
height="$3"

if [ ! -r "$file" ]; then
    echo "File is not readable or does not exist."
    exit 0
fi

# Get mime type
mime=$(file -Lb --mime-type "$file")

case "$mime" in
    inode/directory)
        ls -lh --color=always "$file" | head -n "$height"
        ;;
    text/*|application/json|application/x-sh|application/x-bash|application/x-python|application/javascript|application/xml|text/xml|text/x-tex)
        if command -v bat >/dev/null 2>&1; then
            bat --color=always --style=changes,numbers --terminal-width="$width" "$file" 2>/dev/null | head -n "$height"
        else
            head -n "$height" "$file"
        fi
        ;;
    application/zip)
        if command -v zipinfo >/dev/null 2>&1; then
            zipinfo "$file" | head -n "$height"
        elif command -v unzip >/dev/null 2>&1; then
            unzip -l "$file" | head -n "$height"
        else
            echo "Zip Archive: $file"
        fi
        ;;
    application/x-tar|application/x-gzip|application/x-bzip2|application/x-xz|application/x-compressed-tar)
        tar -tvf "$file" 2>/dev/null | head -n "$height"
        ;;
    application/x-7z-compressed|application/x-rar)
        if command -v 7z >/dev/null 2>&1; then
            7z l "$file" 2>/dev/null | head -n "$height"
        else
            echo "Compressed Archive: $file"
        fi
        ;;
    application/pdf)
        if command -v pdftotext >/dev/null 2>&1; then
            pdftotext -l 10 -nopgbrk -q "$file" - | head -n "$height"
        else
            echo "PDF Document: $file"
            file -b "$file"
        fi
        ;;
    image/*)
        if command -v chafa >/dev/null 2>&1; then
            chafa --size="${width}x${height}" "$file" 2>/dev/null
        elif command -v exiftool >/dev/null 2>&1; then
            exiftool "$file" | head -n "$height"
        else
            echo "Image File: $file"
            file -b "$file"
        fi
        ;;
    *)
        # Check if it's a text file anyway (e.g. scripts without extension)
        if file -b "$file" | grep -q 'text'; then
            if command -v bat >/dev/null 2>&1; then
                bat --color=always --style=changes,numbers --terminal-width="$width" "$file" 2>/dev/null | head -n "$height"
            else
                head -n "$height" "$file"
            fi
        else
            echo "Binary File: $mime"
            file -b "$file"
        fi
        ;;
esac
