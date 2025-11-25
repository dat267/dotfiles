$ErrorActionPreference = 'Stop'

function Install-VSCodePortable {
    [CmdletBinding()]
    param(
        [string]$InstallPath = "$HOME\Apps\VSCode",
        [string]$DownloadUrl = "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-archive"
    )

    if (-not $IsWindows) {
        throw "This script is designed for Windows only. Execution aborted."
    }
    
    $TempDir = Join-Path $env:TEMP "VSCodeUpdate_$([Guid]::NewGuid().Guid.Substring(0,8))"
    $ZipFile = Join-Path $TempDir "vscode.zip"

    if (Get-Process | Where-Object { $_.Path -like "$InstallPath*" }) {
        Write-Error "VS Code is running from $InstallPath. Please close it."
        return
    }

    try {
        New-Item -Path $TempDir -ItemType Directory -Force | Out-Null

        Write-Host "Downloading VS Code..." -ForegroundColor Cyan
        Start-BitsTransfer -Source $DownloadUrl -Destination $ZipFile

        if (Test-Path $InstallPath) {
            Write-Host "Cleaning target directory..." -ForegroundColor Gray
            Remove-Item -Path "$InstallPath\*" -Recurse -Force
        }
        else {
            New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
        }

        Write-Host "Extracting to $InstallPath..." -ForegroundColor Yellow
        Expand-Archive -Path $ZipFile -DestinationPath $InstallPath -Force
        
        Write-Host "Update successful." -ForegroundColor Green
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

Install-VSCodePortable