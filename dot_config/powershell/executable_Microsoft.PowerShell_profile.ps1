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
        # Supported script extensions and default interpreters (easily extensible)
        $scriptResolvers = [ordered]@{
            '.py'  = 'python'
            '.js'  = 'node'
            '.lua' = 'lua'
        }

        # Cache variables globally to optimize lookup performance in hooks
        $escapedExtensions = ($scriptResolvers.Keys | ForEach-Object { [regex]::Escape($_) }) -join '|'
        $global:__script_regex = "(?i)($escapedExtensions)$"
        $global:__script_resolvers = $scriptResolvers

        function global:Get-ScriptResolvers { return $global:__script_resolvers }
        function global:Get-ScriptRegex { return $global:__script_regex }

        # Register script extensions to PATHEXT for tab completion
        $extSet = [System.Collections.Generic.HashSet[string]]::new(($env:PATHEXT -split ';'), [System.StringComparer]::OrdinalIgnoreCase)
        [void]$extSet.Add('.PS1')
        foreach ($ext in (Get-ScriptResolvers).Keys) {
            [void]$extSet.Add($ext.ToUpper())
        }
        $env:PATHEXT = ($extSet | Where-Object { $_ }) -join ';'

        # Set YAZI_FILE_ONE dynamically with fast-path detection and git --exec-path fallback
        if (-not $env:YAZI_FILE_ONE) {
            # 1. Fast static checks (takes <1ms on SSDs)
            $standardPaths = @(
                "$HOME\scoop\apps\git\current\usr\bin\file.exe",
                "C:\Program Files\Git\usr\bin\file.exe"
            )
            foreach ($p in $standardPaths) {
                if ([System.IO.File]::Exists($p)) {
                    $env:YAZI_FILE_ONE = $p
                    break
                }
            }
            # 2. Dynamic exec-path fallback if not found in standard locations (~70ms, runs only if static paths fail)
            if (-not $env:YAZI_FILE_ONE) {
                $gitExec = git --exec-path 2>$null
                if ($gitExec) {
                    $gitRoot = Split-Path (Split-Path (Split-Path $gitExec))
                    $fileExe = [System.IO.Path]::Combine($gitRoot, "usr\bin\file.exe")
                    if ([System.IO.File]::Exists($fileExe)) {
                        $env:YAZI_FILE_ONE = $fileExe
                    }
                }
            }
        }

        # Resolve script files (.py -> python, .js -> node, etc.) using shebangs or extensions.
        # This function handles the actual execution logic, caching dynamically registered functions globally.
        function global:Resolve-ScriptCommand {
            param($path, $LookupArgs)
            
            if ($path) {
                $ext = [System.IO.Path]::GetExtension($path).ToLower()
                $resolvers = Get-ScriptResolvers
                if ($resolvers.Contains($ext)) {
                    $firstLine = $null
                    try {
                        $reader = [System.IO.StreamReader]::new($path)
                        $firstLine = $reader.ReadLine()
                        $reader.Close()
                    } catch {}
                    $interpreter = $null
                    
                    if ($firstLine -and $firstLine -match '^#!\s*(.+)$') {
                        $shebangPath = $Matches[1].Trim()
                        if ($shebangPath -match '/env\s+(\S+)') {
                            $interpreter = $Matches[1]
                        } else {
                            $interpreter = Split-Path $shebangPath -Leaf
                        }
                    }
                    
                    if (-not $interpreter) {
                        $interpreter = $resolvers[$ext]
                    }
                    
                    if ($interpreter) {
                        if ($interpreter -eq 'python3') { $interpreter = 'python' }
                        if ($interpreter -notlike '*.exe') { $interpreter = "$interpreter.exe" }
                        
                        $hash = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($path.ToLower()))).Replace('-', '')
                        $funcName = "script_handler_$hash"
                        if (-not (Get-Command -Name $funcName -CommandType Function -ErrorAction SilentlyContinue)) {
                            $funcDef = "function global:$funcName { & $interpreter `"$path`" @args }"
                            Invoke-Expression $funcDef
                        }
                        $LookupArgs.Command = Get-Command $funcName
                    }
                }
            }
        }

        # Hook into both found and not-found execution paths.
        # This works globally across PATH and the current directory, has 0ms startup overhead,
        # and works instantly for new or edited scripts.
        $ExecutionContext.InvokeCommand.PostCommandLookupAction = {
            param($commandName, $LookupArgs)
            
            if ($global:__in_lookup_hook) { return }
            $global:__in_lookup_hook = $true
            
            try {
                if ($LookupArgs.Command) {
                    $commandType = $LookupArgs.Command.CommandType
                    if ($commandType -eq "Application" -or $commandType -eq "ExternalScript") {
                        $path = $LookupArgs.Command.Path
                        $ext = [System.IO.Path]::GetExtension($path).ToLower()
                        
                        if ($ext -eq '.ps1') {
                            if ($commandName -notmatch '\.ps1$') {
                                $LookupArgs.Command = $null
                            }
                        } else {
                            $regex = Get-ScriptRegex
                            if ($path -match $regex) {
                                if ($commandName -match $regex) {
                                    Resolve-ScriptCommand $path $LookupArgs
                                } else {
                                    $LookupArgs.Command = $null
                                }
                            }
                        }
                    }
                }
            }
            finally {
                $global:__in_lookup_hook = $false
            }
        }

        $ExecutionContext.InvokeCommand.CommandNotFoundAction = {
            param($commandName, $LookupArgs)
            
            if ($global:__in_lookup_hook) { return }
            $global:__in_lookup_hook = $true
            
            try {
                $regex = Get-ScriptRegex
                if ($commandName -notmatch $regex) { return }
                
                $path = $null
                
                if ($commandName -match '[/\\]') {
                    $cleanName = $commandName
                    if ($commandName -match '^get-(.+)$') {
                        $cleanName = $Matches[1]
                    }
                    if ([System.IO.File]::Exists($cleanName)) {
                        $path = [System.IO.Path]::GetFullPath($cleanName)
                    }
                } else {
                    $testPath = [System.IO.Path]::Combine($PWD.Path, $commandName)
                    if ([System.IO.File]::Exists($testPath)) {
                        $path = $testPath
                    } else {
                        if ($commandName -match '^get-(.+)$') {
                            $stripped = $Matches[1]
                            $testPath = [System.IO.Path]::Combine($PWD.Path, $stripped)
                            if ([System.IO.File]::Exists($testPath)) {
                                $path = $testPath
                            }
                        }
                    }
                    
                    if (-not $path) {
                        $pathDirs = $env:PATH -split [IO.Path]::PathSeparator
                        foreach ($dir in $pathDirs) {
                            if (-not [System.IO.Directory]::Exists($dir)) { continue }
                            
                            $testPath = [System.IO.Path]::Combine($dir, $commandName)
                            if ([System.IO.File]::Exists($testPath)) {
                                $path = $testPath
                                break
                            }
                            
                            if ($commandName -match '^get-(.+)$') {
                                $stripped = $Matches[1]
                                $testPath = [System.IO.Path]::Combine($dir, $stripped)
                                if ([System.IO.File]::Exists($testPath)) {
                                    $path = $testPath
                                    break
                                }
                            }
                        }
                    }
                }
                
                if ($path) {
                    Resolve-ScriptCommand $path $LookupArgs
                }
            }
            finally {
                $global:__in_lookup_hook = $false
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

    $fnmCache = Join-Path $HOME ".fnm_env.ps1"
    $shouldRegen = $true
    if ([System.IO.File]::Exists($fnmCache)) {
        $lastWrite = [System.IO.File]::GetLastWriteTime($fnmCache)
        if ((Get-Date) - $lastWrite -lt (New-TimeSpan -Days 1)) {
            $shouldRegen = $false
        }
    }
    if ($shouldRegen -and [bool]($ExecutionContext.SessionState.InvokeCommand.GetCommand('fnm', [System.Management.Automation.CommandTypes]::All))) {
        try {
            $envStr = (fnm env --use-on-cd --shell powershell) -join "`n"
            [System.IO.File]::WriteAllText($fnmCache, $envStr)
            $shouldRegen = $false
        } catch {}
    }
    if ([System.IO.File]::Exists($fnmCache)) {
        . $fnmCache
    }

    # Load machine-local env vars (proxy creds, secrets, etc.) — not tracked in git
    $envLocal = [System.IO.Path]::Combine($HOME, ".env.local")
    if ([System.IO.File]::Exists($envLocal)) {
        foreach ($line in [System.IO.File]::ReadLines($envLocal)) {
            if ($line -match '^\s*[^#]\S+=\S') {
                $k, $v = $line -split '=', 2
                [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim())
            }
        }
    }
}

function codesh { code $PSScriptRoot }
function global:Clear-FnmCache {
    $fnmCache = Join-Path $HOME ".fnm_env.ps1"
    if ([System.IO.File]::Exists($fnmCache)) {
        Remove-Item -Force $fnmCache
    }
}
function resh {
    Clear-FnmCache
    . $PROFILE
}

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

Set-Alias vim nvim
Set-Alias cm chezmoi

function global:Expand-CustomArchive {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Error "'$Path' is not a valid file"
        return
    }
    $ext = [System.IO.Path]::GetExtension($Path).ToLower()
    switch ($ext) {
        '.zip' { Expand-Archive -Path $Path -DestinationPath . }
        '.7z'  { & 7z x $Path }
        '.rar' { & unrar x $Path }
        '.gz'  { & tar -xzf $Path }
        '.tar' { & tar -xf $Path }
        default { Write-Host "Unsupported file extension '$ext'" }
    }
}
Set-Alias extract Expand-CustomArchive

function global:Invoke-Up {
    param($LevelOrName)
    if (-not $LevelOrName) {
        Set-Location ..
        return
    }
    if ($LevelOrName -match '^\d+$') {
        $path = "."
        for ($i = 0; $i -lt [int]$LevelOrName; $i++) {
            $path = Join-Path $path ".."
        }
        Set-Location $path
    } else {
        $current = $pwd.Path
        while ($current -and $current -ne [System.IO.Path]::GetPathRoot($current)) {
            if ((Split-Path $current -Leaf) -ieq $LevelOrName) {
                Set-Location $current
                return
            }
            $current = Split-Path $current -Parent
        }
        Write-Warning "No parent directory matches '$LevelOrName'"
    }
}
Set-Alias up Invoke-Up

function global:Invoke-Which {
    param(
        [Parameter(ValueFromPipeline=$true, Position=0)]
        [string]$Name
    )
    process {
        if (-not $Name) {
            Write-Host "Usage: which <command-name>"
            return
        }
        $cmd = Get-Command -Name $Name -ErrorAction SilentlyContinue
        if ($cmd) {
            if ($cmd.Path) {
                $cmd.Path
            } elseif ($cmd.Source) {
                $cmd.Source
            } else {
                $cmd.Definition
            }
        } else {
            Write-Error "Command '$Name' not found."
        }
    }
}
Set-Alias which Invoke-Which

function global:touch {
    param(
        [Parameter(Mandatory=$true, ValueFromPipeline=$true, Position=0)]
        [string[]]$Path
    )
    process {
        foreach ($p in $Path) {
            if (Test-Path $p) {
                (Get-Item $p).LastWriteTime = Get-Date
            } else {
                New-Item -ItemType File -Path $p -Force | Out-Null
            }
        }
    }
}

function global:sudo {
    param(
        [Parameter(ValueFromRemainingArguments=$true)]
        [string[]]$Arguments
    )
    if (-not $Arguments) {
        # Open an elevated shell in the current directory
        $currentShell = (Get-Process -Id $PID).Path
        Start-Process $currentShell -ArgumentList "-NoProfile -WorkingDirectory `"$PWD`"" -Verb RunAs
        return
    }
    
    $command = $Arguments[0]
    $rest = $Arguments[1..($Arguments.Count - 1)]
    
    # Try to find the command executable path
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    if ($resolved) {
        $execPath = $resolved.Path
        if (-not $execPath) { $execPath = $resolved.Source }
        if ($execPath) {
            Start-Process $execPath -ArgumentList $rest -Verb RunAs -WorkingDirectory $PWD -Wait
        } else {
            # For functions/cmdlets, run inside an elevated PowerShell instance
            $scriptBlock = $Arguments -join ' '
            $currentShell = (Get-Process -Id $PID).Path
            Start-Process $currentShell -ArgumentList "-NoProfile -Command `"$scriptBlock`"" -Verb RunAs -WorkingDirectory $PWD -Wait
        }
    } else {
        # Fallback to direct execution
        Start-Process $command -ArgumentList $rest -Verb RunAs -WorkingDirectory $PWD -Wait
    }
}

# Add grep alias for Select-String if not already in PATH (fast check using .NET to avoid Get-Command overhead)
$hasGrep = $false
foreach ($dir in ($env:PATH -split [IO.Path]::PathSeparator)) {
    if ([System.IO.Directory]::Exists($dir)) {
        if ([System.IO.File]::Exists([System.IO.Path]::Combine($dir, "grep.exe")) -or 
            [System.IO.File]::Exists([System.IO.Path]::Combine($dir, "grep"))) {
            $hasGrep = $true
            break
        }
    }
}
if (-not $hasGrep) {
    Set-Alias grep Select-String -ErrorAction SilentlyContinue
}



function prompt {
    $lastExit = $global:LASTEXITCODE
    $path = $ExecutionContext.SessionState.Path.CurrentLocation.Path -replace [regex]::Escape($HOME), "~"
    $color = if ($lastExit -eq 0) { "$([char]27)[32m" } else { "$([char]27)[31m" }
    $reset = "$([char]27)[0m"
    "$color$path$reset > "
}