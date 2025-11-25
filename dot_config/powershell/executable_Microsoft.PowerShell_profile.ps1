& {
    $env:EDITOR = if ([bool]($ExecutionContext.SessionState.InvokeCommand.GetCommand('nvim', [System.Management.Automation.CommandTypes]::All))) { 'nvim' } else { 'vim' }

    $paths = @(
        "$HOME/.config/powershell/scripts",
        "$HOME/.local/scripts/js",
        "$HOME/.local/scripts/py",
        "$HOME/.local/scripts/lua",
        "$HOME/.local/scripts/ps1",
        "$HOME/.local/bin",
        "$HOME/bin"
    )

    if ($IsWindows) {
        # Setup Go Proxy
        $env:GOPROXY = "https://proxy.golang.org,direct"
        $env:GOSUMDB = "off"

        $paths += "$HOME/.config/powershell/scripts/windows", "$HOME/Apps/nvim-win64/bin", "$HOME/Apps/pwsh", "$HOME/Apps/7z"
        $extSet = [System.Collections.Generic.HashSet[string]]::new(($env:PATHEXT -split ';'), [System.StringComparer]::OrdinalIgnoreCase)
        foreach ($e in @('.PS1', '.PY', '.JS')) { [void]$extSet.Add($e) }
        $env:PATHEXT = ($extSet | Where-Object { $_ }) -join ';'

        # Set YAZI_FILE_ONE dynamically with fast-path detection and git --exec-path fallback
        if (-not $env:YAZI_FILE_ONE) {
            # 1. Fast static checks (takes <1ms on SSDs)
            $standardPaths = @(
                "$HOME\scoop\apps\git\current\usr\bin\file.exe",
                "C:\Program Files\Git\usr\bin\file.exe"
            )
            foreach ($p in $standardPaths) {
                if (Test-Path $p) {
                    $env:YAZI_FILE_ONE = $p
                    break
                }
            }
            # 2. Dynamic exec-path fallback if not found in standard locations (~70ms, runs only if static paths fail)
            if (-not $env:YAZI_FILE_ONE) {
                $gitExec = git --exec-path 2>$null
                if ($gitExec) {
                    $gitRoot = Split-Path (Split-Path (Split-Path $gitExec))
                    $fileExe = Join-Path $gitRoot "usr\bin\file.exe"
                    if (Test-Path $fileExe) {
                        $env:YAZI_FILE_ONE = $fileExe
                    }
                }
            }
        }
    }
    elseif ($IsLinux) { $paths += "$HOME/.config/nvim/bin" }
    elseif ($IsMacOS) { $paths += "/opt/homebrew/bin" }

    $set = [System.Collections.Generic.HashSet[string]]::new($env:PATH -split [IO.Path]::PathSeparator, [System.StringComparer]::OrdinalIgnoreCase)
    foreach ($p in $paths) {
        if ([System.IO.Directory]::Exists($p)) { [void]$set.Add($p) }
    }
    $env:PATH = $set -join [IO.Path]::PathSeparator

    $mod = "$HOME/.config/powershell/modules"
    if ([System.IO.Directory]::Exists($mod)) {
        foreach ($f in [System.IO.Directory]::GetFiles($mod, "*.psm1")) {
            Import-Module $f -ErrorAction SilentlyContinue
        }
    }

    if ([bool]($ExecutionContext.SessionState.InvokeCommand.GetCommand('fnm', [System.Management.Automation.CommandTypes]::All))) {
        & ([scriptblock]::Create(((fnm env --use-on-cd --shell powershell) -join "`n")))
    }

    # Load machine-local env vars (proxy creds, secrets, etc.) — not tracked in git
    $envLocal = Join-Path $HOME ".env.local"
    if (Test-Path $envLocal) {
        Get-Content $envLocal | Where-Object { $_ -match '^\s*[^#]\S+=\S' } | ForEach-Object {
            $k, $v = $_ -split '=', 2
            [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim())
        }
    }
}

function codesh { code $PSScriptRoot }
function resh { . $PROFILE }

function y {
    $tmp = [System.IO.Path]::GetTempFileName()
    yazi $args --cwd-file="$tmp"
    if (Test-Path $tmp) {
        $cwd = Get-Content -Path $tmp -Encoding UTF8
        if (-not [String]::IsNullOrEmpty($cwd) -and $cwd -ne $PWD.Path) {
            Set-Location -LiteralPath ([System.IO.Path]::GetFullPath($cwd))
        }
        Remove-Item -Path $tmp
    }
}

Set-Alias cw Open-LogsInsights
Set-Alias vim nvim
Set-Alias cm chezmoi

function prompt {
    $lastExit = $global:LASTEXITCODE
    $path = $ExecutionContext.SessionState.Path.CurrentLocation.Path -replace [regex]::Escape($HOME), "~"
    $color = if ($lastExit -eq 0) { "$([char]27)[32m" } else { "$([char]27)[31m" }
    $reset = "$([char]27)[0m"
    "$color$path$reset > "
}