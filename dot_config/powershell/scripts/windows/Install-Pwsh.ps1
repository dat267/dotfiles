$ErrorActionPreference = 'Stop'

function Install-PowerShell {
    [CmdletBinding()]
    param(
        [string]$InstallPath = "$HOME\Apps\pwsh",
        [string]$Architecture = "win-x64"
    )
    
    if (-not $IsWindows) {
        throw "This script is designed for Windows only. Execution aborted."
    }

    $TempDir = Join-Path $env:TEMP "pwshUpdate_$([Guid]::NewGuid().Guid.Substring(0,8))"
    $ZipFile = Join-Path $TempDir "PowerShell.zip"
    $ApiUrl = "https://api.github.com/repos/PowerShell/PowerShell/releases/latest"

    if ($Host.Name -ne "ConsoleHost") {
        Write-Error "Script requires native Windows PowerShell ConsoleHost."
        return
    }

    if (Get-Process | Where-Object { $_.Path -like "$InstallPath*" }) {
        Write-Error "Close all running pwsh instances in $InstallPath before proceeding."
        return
    }

    try {
        New-Item -Path $TempDir -ItemType Directory -Force | Out-Null
        
        Write-Host "Resolving latest release..." -ForegroundColor Cyan
        $Release = Invoke-RestMethod -Uri $ApiUrl
        $DownloadUrl = $Release.assets | 
        Where-Object { $_.name -like "*$Architecture.zip" } | 
        Select-Object -ExpandProperty browser_download_url

        Write-Host "Downloading $Architecture package..." -ForegroundColor Cyan
        Start-BitsTransfer -Source $DownloadUrl -Destination $ZipFile

        if (Test-Path $InstallPath) {
            Write-Host "Removing existing installation..." -ForegroundColor Gray
            Remove-Item -Path $InstallPath -Recurse -Force
        }
        
        New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null

        Write-Host "Extracting files to $InstallPath..." -ForegroundColor Yellow
        Expand-Archive -Path $ZipFile -DestinationPath $InstallPath -Force

        $Executable = Join-Path $InstallPath "pwsh.exe"
        if (Test-Path $Executable) {
            Write-Host "Successfully installed to $InstallPath" -ForegroundColor Green
        }
    }
    catch {
        Write-Error "Deployment failed: $($_.Exception.Message)"
    }
    finally {
        if (Test-Path $TempDir) {
            Remove-Item -Path $TempDir -Recurse -Force
        }
    }
}

Install-PowerShell