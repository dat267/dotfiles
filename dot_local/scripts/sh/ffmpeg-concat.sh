#!/bin/bash

# Exit on error
set -e

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed or not in PATH."
    read -p "Press Enter to exit..."
    exit 1
fi

if [ "$#" -lt 2 ]; then
    echo "Error: You must select at least 2 files to concatenate."
    read -p "Press Enter to exit..."
    exit 1
fi

first_file="$1"
ext="${first_file##*.}"

echo "========================================"
echo "      FFmpeg Video Concatenator         "
echo "========================================"
echo "Selected files in order:"
for f in "$@"; do
    echo "  - $(basename "$f")"
done
echo "========================================"

echo "Select concatenation mode:"
echo "  [1] Fast Concat (No Re-encoding) - Instant, but files must have identical resolution/codecs."
echo "  [2] Safe Concat (Re-encode)      - Slower, but works with mixed resolution/codecs."
read -p "Enter choice [1/2] (default: 1): " mode
mode=${mode:-1}

read -p "Enter output filename (default: combined.$ext): " output_name
output_name=${output_name:-combined.$ext}

# Temporary file list for demuxer (mode 1)
tmp_list=$(mktemp)

if [ "$mode" -eq 1 ]; then
    echo "Preparing file list..."
    for f in "$@"; do
        # Absolute path is required for -safe 0
        abs_path=$(realpath "$f")
        # Escape single quotes in filenames for ffmpeg concat file
        escaped_path=$(echo "$abs_path" | sed "s/'/'\\\\''/g")
        echo "file '$escaped_path'" >> "$tmp_list"
    done

    echo "Running fast concatenation..."
    if ffmpeg -f concat -safe 0 -i "$tmp_list" -c copy -y "$output_name"; then
        echo "Successfully concatenated to '$output_name'!"
    else
        echo "Error: Fast concatenation failed. Codecs/parameters might not match."
        echo "Try running again with Mode 2 (Re-encode)."
    fi
else
    echo "Building re-encode filter graph..."
    inputs=()
    filter=""
    count=0
    for f in "$@"; do
        inputs+=("-i" "$f")
        filter="${filter}[${count}:v][${count}:a]"
        count=$((count + 1))
    done
    filter="${filter} concat=n=${count}:v=1:a=1 [v][a]"
    
    echo "Running safe concatenation (re-encoding)..."
    if ffmpeg "${inputs[@]}" -filter_complex "$filter" -map "[v]" -map "[a]" -c:v libx264 -c:a aac -y "$output_name"; then
        echo "Successfully concatenated and re-encoded to '$output_name'!"
    else
        echo "Error: Concatenation failed."
    fi
fi

rm -f "$tmp_list"
echo ""
read -p "Press Enter to close."
