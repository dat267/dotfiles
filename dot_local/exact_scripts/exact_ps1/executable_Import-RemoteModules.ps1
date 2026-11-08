function Import-RemoteModules {
    <#
    .SYNOPSIS
        Dynamically imports PowerShell modules from a GitHub repository into the current session.
    .DESCRIPTION
        Fetches .psm1 files from the 'dat267/dotfiles' repository, creates in-memory modules 
        using a 'dat267' namespace prefix, and ensures no duplicate instances are created.
    .NOTES
        Remote Execution One-Liner:
        irm bit.ly/dat-pwsh | iex
    #>
    [CmdletBinding()]
    param()

    $ErrorActionPreference = 'Stop'
    $Owner = "dat267"
    $Repo = "dotfiles"
    $Prefix = "dat267"
    $ModuleFolder = "dot_config/powershell/modules"
    $ApiUrl = "https://api.github.com/repos/$Owner/$Repo/contents/$ModuleFolder"
    
    try {
        $Files = Invoke-RestMethod -Uri $ApiUrl -Method Get
        foreach ($File in ($Files | Where-Object { $_.name -like "*.psm1" })) {
            $CodeString = Invoke-RestMethod -Uri $File.download_url
            if (-not [string]::IsNullOrWhiteSpace($CodeString)) {
                $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($File.name)
                $FullName = "$Prefix.$BaseName"
                if (Get-Module -Name $FullName) {
                    Remove-Module -Name $FullName -ErrorAction SilentlyContinue
                }
                $ScriptBlock = [scriptblock]::Create($CodeString)
                New-Module -Name $FullName -ScriptBlock $ScriptBlock | Import-Module
                Write-Host "Imported Module: $FullName" -ForegroundColor Green
            }
        }
    }
    catch {
        Write-Error "Failed to import remote modules: $($_.Exception.Message)"
    }
}

Import-RemoteModules