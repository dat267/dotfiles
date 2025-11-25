$ErrorActionPreference = 'Stop'
function Install-FirefoxPortable {
    [CmdletBinding()]
    param(
        [string]$InstallPath = "$HOME\Apps\Firefox",
        [string]$SevenZipUrl = "https://www.7-zip.org/a/7zr.exe",
        [string]$FirefoxUrl = "https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US&archive=zip"
    )

    if (-not $IsWindows) {
        throw "This script is designed for Windows only. Execution aborted."
    }

    $TempDir = Join-Path $env:TEMP "FirefoxUpdate_$([Guid]::NewGuid().Guid.Substring(0,8))"
    $SevenZipExe = Join-Path $TempDir "7zr.exe"
    $ArchiveFile = Join-Path $TempDir "FirefoxSetup.7z"
    $ExtractPath = Join-Path $TempDir "Extracted"

    if (Get-Process | Where-Object { $_.Path -like "$InstallPath*" }) {
        Write-Error "Firefox is currently running from the installation path. Please close it."
        return
    }

    try {
        New-Item -Path $TempDir, $ExtractPath -ItemType Directory -Force | Out-Null

        Write-Host "Downloading 7-Zip and Firefox archive..." -ForegroundColor Cyan
        Start-BitsTransfer -Source $SevenZipUrl -Destination $SevenZipExe
        Start-BitsTransfer -Source $FirefoxUrl -Destination $ArchiveFile

        Write-Host "Extracting payload..." -ForegroundColor Yellow
        $ArgumentList = @("x", $ArchiveFile, "-o$ExtractPath", "-y")
        Start-Process -FilePath $SevenZipExe -ArgumentList $ArgumentList -Wait -NoNewWindow

        $SourceDir = (Get-ChildItem -Path $ExtractPath -Directory | 
            Where-Object { $_.Name -match 'core|firefox' } | 
            Select-Object -First 1).FullName

        if (-not $SourceDir) { throw "Could not locate source directory in extracted files." }

        if (Test-Path $InstallPath) {
            Write-Host "Cleaning target directory..." -ForegroundColor Gray
            Remove-Item -Path "$InstallPath\*" -Recurse -Force
        }
        else {
            New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
        }

        Write-Host "Deploying to $InstallPath..." -ForegroundColor Green
        Copy-Item -Path "$SourceDir\*" -Destination $InstallPath -Recurse -Force
    }
    catch {
        Write-Error "Update failed: $($_.Exception.Message)"
    }
    finally {
        if (Test-Path $TempDir) {
            Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Install-FirefoxPortable