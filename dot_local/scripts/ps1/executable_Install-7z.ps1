<#
.SYNOPSIS
    Downloads and installs 7-Zip silently and adds it to the system PATH on Windows.
.DESCRIPTION
    This script checks for Administrator privileges, attempts to install 7-Zip using winget,
    falls back to downloading the official installer from 7-zip.org if winget is unavailable,
    and ensures the installation directory is added to the system PATH.
#>

# 1. Require Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "This script must be run as an Administrator to modify System PATH and install software."
    Write-Host "Attempting to elevate privileges..."
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

# 2. Define target installation path
$installDir = "C:\Program Files\7-Zip"
$exePath = "$installDir\7z.exe"

# 3. Install 7-Zip
if (Get-Command 7z -ErrorAction SilentlyContinue) {
    Write-Output "7-Zip is already installed and in the PATH."
} elseif (Test-Path $exePath) {
    Write-Output "7-Zip is installed in '$installDir' but not in PATH."
} else {
    Write-Output "7-Zip is not installed. Attempting to install..."
    
    # Try winget first
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Output "Installing 7-Zip via winget..."
        winget install --id 7zip.7zip --silent --accept-source-agreements --accept-package-agreements
    } else {
        # Fallback to downloading installer from website
        Write-Output "winget not found. Downloading 7-Zip from official website..."
        $url = "https://7-zip.org/a/7z2408-x64.msi"
        $installerPath = "$env:TEMP\7z_installer.msi"
        
        try {
            Invoke-WebRequest -Uri $url -OutFile $installerPath -ErrorAction Stop
            Write-Output "Installing silently..."
            Start-Process msiexec.exe -ArgumentList "/i `"$installerPath`" /qn /norestart" -Wait -NoNewWindow
        } catch {
            Write-Error "Failed to download/install 7-Zip: $_"
            Exit 1
        } finally {
            if (Test-Path $installerPath) {
                Remove-Item $installerPath -Force
            }
        }
    }
}

# 4. Add to System PATH if not already present
if (Test-Path $exePath) {
    Write-Output "Ensuring 7-Zip is in the System PATH..."
    $systemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    
    if ($systemPath -split ";" -notcontains $installDir) {
        [Environment]::SetEnvironmentVariable("Path", "$systemPath;$installDir", "Machine")
        Write-Output "Successfully added '$installDir' to System PATH."
        Write-Output "NOTE: You may need to restart your terminal or Yazi for the changes to take effect."
    } else {
        Write-Output "'$installDir' is already in the System PATH."
    }
} else {
    Write-Error "7-Zip installation verification failed. Could not find 7z.exe at '$exePath'."
    Exit 1
}

Write-Output "Installation complete!"


