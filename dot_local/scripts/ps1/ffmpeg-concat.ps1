# Exit on error
$ErrorActionPreference = "Stop"

# Check if ffmpeg is installed
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "Error: ffmpeg is not installed or not in PATH."
    Read-Host "Press Enter to exit..."
    Exit 1
}

if ($args.Count -lt 2) {
    Write-Warning "Error: You must select at least 2 files to concatenate."
    Read-Host "Press Enter to exit..."
    Exit 1
}

$firstFile = $args[0]
$ext = [System.IO.Path]::GetExtension($firstFile)

Write-Host "========================================"
Write-Host "      FFmpeg Video Concatenator         "
Write-Host "========================================"
Write-Host "Selected files in order:"
foreach ($f in $args) {
    Write-Host "  - $(Split-Path $f -Leaf)"
}
Write-Host "========================================"

Write-Host "Select concatenation mode:"
Write-Host "  [1] Fast Concat (No Re-encoding) - Instant, but files must have identical resolution/codecs."
Write-Host "  [2] Safe Concat (Re-encode)      - Slower, but works with mixed resolution/codecs."
$mode = Read-Host "Enter choice [1/2] (default: 1)"
if ([string]::IsNullOrEmpty($mode)) { $mode = 1 }

$outputName = Read-Host "Enter output filename (default: combined$ext)"
if ([string]::IsNullOrEmpty($outputName)) { $outputName = "combined$ext" }

# Temporary file list for demuxer (mode 1)
$tmpList = [System.IO.Path]::GetTempFileName()

try {
    if ($mode -eq 1) {
        Write-Host "Preparing file list..."
        foreach ($f in $args) {
            $absPath = [System.IO.Path]::GetFullPath($f)
            $escaped = $absPath -replace "'", "'\''"
            Add-Content -Path $tmpList -Value "file '$escaped'"
        }

        Write-Host "Running fast concatenation..."
        & ffmpeg -f concat -safe 0 -i $tmpList -c copy -y $outputName
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Successfully concatenated to '$outputName'!"
        } else {
            Write-Warning "Error: Fast concatenation failed. Codecs/parameters might not match."
            Write-Warning "Try running again with Mode 2 (Re-encode)."
        }
    } else {
        Write-Host "Building re-encode filter graph..."
        $inputs = @()
        $filter = ""
        $count = 0
        foreach ($f in $args) {
            $inputs += "-i"
            $inputs += $f
            $filter += "[${count}:v][${count}:a]"
            $count++
        }
        $filter += " concat=n=${count}:v=1:a=1 [v][a]"
        
        Write-Host "Running safe concatenation (re-encoding)..."
        $allArgs = $inputs + @("-filter_complex", $filter, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", "-y", $outputName)
        & ffmpeg $allArgs
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Successfully concatenated and re-encoded to '$outputName'!"
        } else {
            Write-Warning "Error: Concatenation failed."
        }
    }
} finally {
    if (Test-Path $tmpList) {
        Remove-Item $tmpList -Force
    }
}

Write-Host ""
Read-Host "Press Enter to close."
