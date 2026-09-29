# Report a failing CI step without the job log (that needs repo admin rights).
#
#   . .github/scripts/step-report.ps1
#   Invoke-WithReport "chezmoi-render" {
#       Invoke-Native "chezmoi apply" { & $chezmoi apply --force }
#   }
#
# Invoke-WithReport turns a failure into an ::error:: annotation carrying the
# tail of the error, plus the full text in the step summary. Both render on the
# public run page, unlike the job log. Invoke-Native captures a native command's
# output so its stderr reaches that annotation instead of only the hidden log —
# no transcript, which the runner's PowerShell host may not support.

$ErrorActionPreference = 'Stop'

function Invoke-Native {
    param([string]$Label, [scriptblock]$Command)
    $output = & $Command 2>&1
    $code = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    if ($code -ne 0) { throw "$Label exited $code`: $($output -join ' / ')" }
    $output
}

function Invoke-WithReport {
    param([string]$Name, [scriptblock]$Body)
    try {
        & $Body
    }
    catch {
        $detail = ($_ | Out-String).Trim()
        Add-Content $env:GITHUB_STEP_SUMMARY "## $Name failed"
        Add-Content $env:GITHUB_STEP_SUMMARY '```'
        Add-Content $env:GITHUB_STEP_SUMMARY $detail
        Add-Content $env:GITHUB_STEP_SUMMARY '```'
        $tail = ($detail -split "`r?`n" | Where-Object { $_.Trim() } |
            Select-Object -Last 8) -join ' | '
        "::error::$Name failed: $tail"
        throw
    }
}
