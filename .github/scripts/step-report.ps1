# Run one CI step body with its output captured, so a failure is readable
# without the job log (that needs repo admin rights).
#
#   . .github/scripts/step-report.ps1
#   Invoke-WithReport "chezmoi-render" {
#       & $tool @args
#       if ($LASTEXITCODE -ne 0) { throw "tool exited $LASTEXITCODE" }
#   }
#
# On failure the transcript goes to the step summary (public on the run page)
# and its last lines become an annotation, which GitHub renders at the failure
# position.

function Invoke-WithReport {
    param([string]$Name, [scriptblock]$Body)
    $log = Join-Path $env:RUNNER_TEMP "$Name.log"
    Start-Transcript -Path $log -Force | Out-Null
    try {
        & $Body
        if ($LASTEXITCODE -ne 0) { throw "$Name exited $LASTEXITCODE" }
    }
    catch {
        Stop-Transcript | Out-Null
        Add-Content $env:GITHUB_STEP_SUMMARY "## $Name output"
        Add-Content $env:GITHUB_STEP_SUMMARY '```'
        Get-Content $log | Add-Content $env:GITHUB_STEP_SUMMARY
        Add-Content $env:GITHUB_STEP_SUMMARY '```'
        $tail = (Get-Content $log | Select-Object -Last 8) -join ' | '
        "::error::$Name failed: $tail"
        throw
    }
    Stop-Transcript | Out-Null
}
