<#
.SYNOPSIS
    Downloads and executes a PowerShell script hosted on OneDrive via Microsoft Graph.

.DESCRIPTION
    This script authenticates to Microsoft Graph, converts a OneDrive sharing URL 
    into a compatible ShareID, and streams the script content directly into 
    memory for execution.

.PREREQUISITES
    1. Install the Microsoft Graph Authentication module:
       Install-Module Microsoft.Graph.Authentication -Scope CurrentUser

    2. An active internet connection to reach graph.microsoft.com.

.NOTES
    - Scopes: Requires 'Files.Read.All' and 'Sites.Read.All'.
    - Authentication: A browser window will open for device login upon execution.
    - Security: Only run this if you trust the source of the $ScriptUrl.
#>
param(
    [Parameter(Mandatory = $true)][string]$ScriptUrl,
    [Parameter(Mandatory = $false)][hashtable]$ScriptParameters = @{},
    [switch]$Preview
)
#Requires -Modules Microsoft.Graph.Authentication
Connect-MgGraph -NoWelcome -Scopes "Files.Read.All", "Sites.Read.All"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($ScriptUrl)
$base64 = [System.Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
$shareId = "u!$base64"
$item = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/shares/$shareId/driveItem"
if ($item.name -notlike "*.ps1" -or -not $item.file) {
    throw "Error: Invalid file type ($($item.name))"
}
$scriptText = Invoke-RestMethod -Uri $item.'@microsoft.graph.downloadUrl'
if ($Preview) {
    Write-Host "--- PREVIEW: $($item.name) ---" -ForegroundColor Cyan
    $scriptText
    return
}
& ([scriptblock]::Create($scriptText)) @ScriptParameters