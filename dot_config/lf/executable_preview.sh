#!/bin/sh
# lf previewer script optimized for rich previews

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
        if command -v tree >/dev/null 2>&1; then
            tree -C -L 2 --dirsfirst "$file" | head -n "$height"
        else
            ls -lh --color=always "$file" | head -n "$height"
        fi
        ;;
    text/html)
        if command -v pandoc >/dev/null 2>&1; then
            pandoc -t plain "$file" 2>/dev/null | head -n "$height"
        elif command -v bat >/dev/null 2>&1; then
            bat --color=always --style=changes,numbers --terminal-width="$width" "$file" 2>/dev/null | head -n "$height"
        else
            head -n "$height" "$file"
        fi
        ;;
    application/vnd.openxmlformats-officedocument.wordprocessingml.document|\
    application/vnd.oasis.opendocument.text|\
    application/epub+zip)
        if command -v pandoc >/dev/null 2>&1; then
            pandoc -t plain "$file" 2>/dev/null | head -n "$height"
        else
            echo "Office/Epub Document: $mime"
            file -b "$file"
        fi
        ;;
    video/*|audio/*)
        if command -v ffprobe >/dev/null 2>&1; then
            echo "--- Media Info ---"
            ffprobe -v error -show_format -show_streams "$file" 2>/dev/null \
                | grep -E '^(filename|format_name|duration|size|bit_rate|codec_name|width|height|sample_rate|channels|TAG:title|TAG:artist)=' \
                | sed 's/TAG://'
        else
            echo "Media File: $mime"
            file -b "$file"
        fi
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
