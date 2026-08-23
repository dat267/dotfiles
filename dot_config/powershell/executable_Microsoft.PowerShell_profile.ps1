if ($global:__dotfiles_profile_loaded) { return }
$global:__dotfiles_profile_loaded = $true

& {
    $env:EDITOR = if (Get-Command nvim -ErrorAction SilentlyContinue) { 'nvim' } elseif (Get-Command vim -ErrorAction SilentlyContinue) { 'vim' } elseif (Get-Command hx -ErrorAction SilentlyContinue) { 'hx' } elseif (Get-Command helix -ErrorAction SilentlyContinue) { 'helix' } else { 'vi' }

    $paths = @(
        "$HOME/.config/powershell/scripts",
        "$HOME/.local/scripts/py",
        "$HOME/.local/scripts/lua",
        "$HOME/.local/scripts/ps1",
        "$HOME/.local/bin",
        "$HOME/bin"
    )

    if ($IsWindows) {
        $paths += @(
            "$HOME/.config/powershell/scripts/windows",
            "$HOME/Apps/nvim-win64/bin",
            "$HOME/Apps/pwsh",
            "$HOME/Apps/7z"
        )
    }
    elseif ($IsLinux) {
        $paths += "$HOME/.config/nvim/bin"
    }
    elseif ($IsMacOS) {
        $paths += "/opt/homebrew/bin"
    }

    $set = [System.Collections.Generic.HashSet[string]]::new($env:PATH -split [IO.Path]::PathSeparator, [System.StringComparer]::OrdinalIgnoreCase)
    foreach ($p in $paths) {
        if ([System.IO.Directory]::Exists($p)) { [void]$set.Add($p) }
    }
    $env:PATH = $set -join [IO.Path]::PathSeparator

    if ($IsWindows) {
        $env:GOPROXY = "https://proxy.golang.org,direct"
        $env:GOSUMDB = "off"

        Set-ItemProperty -Path "HKCU:\Console" -Name "VirtualTerminalLevel" -Value 1 -Type DWord -ErrorAction SilentlyContinue

        $scriptResolvers = [ordered]@{
            '.py'  = 'python'
            '.js'  = 'node'
            '.lua' = 'lua'
        }

        $escapedExtensions = ($scriptResolvers.Keys | ForEach-Object { [regex]::Escape($_) }) -join '|'
        $global:__script_regex = "(?i)($escapedExtensions)$"
        $global:__script_resolvers = $scriptResolvers

        function global:Get-ScriptResolvers { $global:__script_resolvers }
        function global:Get-ScriptRegex { $global:__script_regex }

        $extSet = [System.Collections.Generic.HashSet[string]]::new(($env:PATHEXT -split ';'), [System.StringComparer]::OrdinalIgnoreCase)
        [void]$extSet.Add('.PS1')
        foreach ($ext in (Get-ScriptResolvers).Keys) {
            [void]$extSet.Add($ext.ToUpper())
        }
        $env:PATHEXT = ($extSet | Where-Object { $_ }) -join ';'

        if (-not $env:YAZI_FILE_ONE) {
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

        function global:Resolve-ScriptCommand {
            param($path, $LookupArgs)
            if ($path) {
                $ext = [System.IO.Path]::GetExtension($path).ToLower()
                $resolvers = Get-ScriptResolvers
                if ($resolvers.Contains($ext)) {
                    $interpreter = $resolvers[$ext]
                    if ($interpreter -eq 'python3') { $interpreter = 'python' }
                    if ($interpreter -notlike '*.exe') { $interpreter = "$interpreter.exe" }
                    $funcName = "script_handler_" + ($path.ToLower() -replace '[^a-zA-Z0-9]', '_')
                    if (-not (Get-Command -Name $funcName -CommandType Function -ErrorAction SilentlyContinue)) {
                        $scriptBlock = [scriptblock]::Create("& '$interpreter' '$path' `$args")
                        Set-Item -Path "function:global:$funcName" -Value $scriptBlock
                    }
                    $LookupArgs.Command = Get-Command $funcName
                }
            }
        }

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
                        if ($ext -ne '.ps1') {
                            $regex = Get-ScriptRegex
                            if ($path -match $regex) {
                                if ($commandName -match $regex) {
                                    Resolve-ScriptCommand $path $LookupArgs
                                }
                                else {
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
                }
                else {
                    $testPath = [System.IO.Path]::Combine($PWD.Path, $commandName)
                    if ([System.IO.File]::Exists($testPath)) {
                        $path = $testPath
                    }
                    else {
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

    $mod = "$HOME/.config/powershell/modules"
    if ([System.IO.Directory]::Exists($mod)) {
        foreach ($f in [System.IO.Directory]::GetFiles($mod, "*.psm1")) {
            Import-Module $f -ErrorAction SilentlyContinue
        }
    }

    if ($IsWindows) {
        # --- Proxy credentials (user environment variables) ---
        # Proxy creds are stored as full URLs in USER-scope HTTP_PROXY /
        # HTTPS_PROXY / http_proxy / https_proxy (plaintext, accepted tradeoff).
        # They are inherited into the process env at login, so the profile does
        # zero proxy work at startup — no Add-Type, no P/Invoke, no compile.

        function global:Set-ProxyCredential {
            [CmdletBinding()]
            param(
                [string]$UserName,
                [securestring]$Password
            )

            # Local helpers (scoped to this function, nothing leaks to the
            # global namespace). Parse HKCU ProxyServer into scheme -> host:port,
            # handling "http=a:8080;https=b:9090" and bare "host:port".
            function ConvertFrom-ProxyServer {
                param([string]$ProxyServer)
                if (-not $ProxyServer) { return @{} }
                $result = @{}
                if ($ProxyServer -match '=') {
                    foreach ($part in ($ProxyServer -split ';')) {
                        if ($part -match '^([^=]+)=(.+)$') {
                            $result[$Matches[1].Trim().ToLower()] = $Matches[2].Trim()
                        }
                    }
                } else {
                    $result['http'] = $ProxyServer.Trim()
                    $result['https'] = $ProxyServer.Trim()
                }
                $result
            }
            # Build an http:// proxy URL, URL-escaped user:pass, or no auth.
            function ConvertTo-ProxyUrl {
                param([string]$HostPort, [string]$UserName, [string]$Password)
                if (-not $HostPort) { return $null }
                if ($UserName -and $Password) {
                    return "http://$([uri]::EscapeDataString($UserName))`:$([uri]::EscapeDataString($Password))@$HostPort"
                }
                return "http://$HostPort"
            }

            if (-not $UserName) { $UserName = Read-Host 'Proxy username' }
            if (-not $Password) { $Password = Read-Host 'Proxy password' -AsSecureString }
            if ($Password.Length -eq 0) {
                Write-Warning "Set-ProxyCredential: empty password; not saving partial credentials."
                return
            }

            $cfg = Test-ProxyConfig
            if (-not $cfg.ProxyServer) {
                Write-Warning "Set-ProxyCredential: no system proxy host:port found; cannot build proxy URL."
                return
            }
            $schemes = ConvertFrom-ProxyServer $cfg.ProxyServer
            $hostPort = $schemes['http']
            if (-not $hostPort) { $hostPort = $schemes['https'] }
            if (-not $hostPort) {
                Write-Warning "Set-ProxyCredential: no http/https host:port in system proxy; cannot build proxy URL."
                return
            }

            $plain = [Runtime.InteropServices.Marshal]::PtrToStringUni(
                [Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($Password))
            $url = ConvertTo-ProxyUrl -HostPort $hostPort -UserName $UserName -Password $plain

            foreach ($name in 'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy') {
                [Environment]::SetEnvironmentVariable($name, $url, 'User')
            }
            $env:HTTP_PROXY = $url
            $env:HTTPS_PROXY = $url
            $env:http_proxy = $url
            $env:https_proxy = $url
            Write-Host "Proxy URL saved to user environment: $url"
        }

        function global:Get-ProxyCredential {
            $url = $env:HTTP_PROXY
            if (-not $url) { $url = [Environment]::GetEnvironmentVariable('HTTP_PROXY', 'User') }
            if (-not $url) { return $null }
            return $url
        }

        function global:Clear-ProxyCredential {
            foreach ($name in 'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy') {
                [Environment]::SetEnvironmentVariable($name, $null, 'User')
            }
            Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY, Env:http_proxy, Env:https_proxy -ErrorAction SilentlyContinue
            Write-Host 'Proxy URL removed from user environment.'
        }

        function global:Test-ProxyConfig {
            $p = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
            [pscustomobject]@{
                ProxyEnable   = [int]$p.ProxyEnable
                ProxyServer   = [string]$p.ProxyServer
                ProxyOverride = [string]$p.ProxyOverride
            }
        }

        # --- End proxy credentials ---
    }

    $global:__home_regex = [regex]::Escape($HOME)
}

function codesh { code $PSScriptRoot }

function resh {
    $global:__dotfiles_profile_loaded = $false
    . $PROFILE
}

function y {
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        yazi @args --cwd-file="$tmp"
        if (Test-Path $tmp) {
            $cwd = Get-Content -Path $tmp -Encoding UTF8
            if (-not [string]::IsNullOrEmpty($cwd) -and $cwd -ne $PWD.Path) {
                Set-Location -LiteralPath $cwd
            }
        }
    }
    finally {
        if (Test-Path $tmp) {
            Remove-Item -Path $tmp -Force
        }
    }
}

function global:codeat {
    param([string]$Path = '.')
    $target = Resolve-Path $Path -ErrorAction Stop
    code $target -r
}

Set-Alias vim nvim
Set-Alias hx helix

function global:Expand-CustomArchive {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Error "'$Path' is not a valid file"
        return
    }
    $ext = [System.IO.Path]::GetExtension($Path).ToLower()
    switch ($ext) {
        '.zip' { Expand-Archive -Path $Path -DestinationPath . }
        '.7z' { if (Get-Command 7z -ErrorAction SilentlyContinue) { & 7z x $Path } else { Write-Error "7z not found" } }
        '.rar' { if (Get-Command unrar -ErrorAction SilentlyContinue) { & unrar x $Path } else { Write-Error "unrar not found" } }
        '.gz' { & tar -xzf $Path }
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
    }
    else {
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

function global:..  { Set-Location .. }
function global:... { Set-Location ../.. }

function global:Invoke-Which {
    param(
        [Parameter(ValueFromPipeline = $true, Position = 0)]
        [string]$Name,
        [switch]$All
    )
    process {
        if (-not $Name) {
            Write-Host "Usage: which <command-name>"
            return
        }
        $cmds = Get-Command -Name $Name -All -ErrorAction SilentlyContinue
        if (-not $All) { $cmds = $cmds | Select-Object -First 1 }
        if ($cmds) {
            foreach ($cmd in $cmds) {
                if ($cmd.Path) { $cmd.Path }
                elseif ($cmd.Source) { $cmd.Source }
                else { $cmd.Definition }
            }
        }
        else {
            Write-Error "Command '$Name' not found."
        }
    }
}
Set-Alias which Invoke-Which

function global:touch {
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true, Position = 0)]
        [string[]]$Path
    )
    process {
        foreach ($p in $Path) {
            if (Test-Path $p) {
                (Get-Item $p).LastWriteTime = Get-Date
            }
            else {
                New-Item -ItemType File -Path $p -Force | Out-Null
            }
        }
    }
}

function global:sudo {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    if (-not $Arguments) {
        $currentShell = (Get-Process -Id $PID).Path
        Start-Process $currentShell -ArgumentList "-NoProfile -WorkingDirectory `"$PWD`"" -Verb RunAs
        return
    }
    $command = $Arguments[0]
    $rest = if ($Arguments.Length -gt 1) { $Arguments[1..($Arguments.Length - 1)] } else { @() }
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    if ($resolved) {
        $execPath = $resolved.Path
        if (-not $execPath) { $execPath = $resolved.Source }
        if ($execPath) {
            Start-Process $execPath -ArgumentList $rest -Verb RunAs -WorkingDirectory $PWD -Wait
        }
        else {
            $scriptBlock = $Arguments -join ' '
            $currentShell = (Get-Process -Id $PID).Path
            Start-Process $currentShell -ArgumentList "-NoProfile -Command `"$scriptBlock`"" -Verb RunAs -WorkingDirectory $PWD -Wait
        }
    }
    else {
        Start-Process $command -ArgumentList $rest -Verb RunAs -WorkingDirectory $PWD -Wait
    }
}

if (-not (Get-Command grep -ErrorAction SilentlyContinue)) {
    Set-Alias grep Select-String -ErrorAction SilentlyContinue
}

function global:mtmp {
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    Set-Location $tmp
}

function global:mkcd {
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$Path
    )
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    Set-Location $Path
}

function global:gacp {
    param(
        [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
        [string[]]$Message
    )
    process {
        $branch = (git rev-parse --abbrev-ref HEAD 2>$null)
        if (-not $branch) {
            Write-Error "Not a git repository."
            return
        }
        git pull origin $branch
        if ($LASTEXITCODE -eq 0) {
            git add -A
            git commit -m ($Message -join ' ')
            if ($LASTEXITCODE -eq 0) {
                git push origin $branch
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Bash-equivalent utilities
# ---------------------------------------------------------------------------

# ls variants
function global:ll  { Get-ChildItem -Force @args | Format-Table Mode, LastWriteTime, Length, Name -AutoSize }
function global:la  { Get-ChildItem -Force @args }
function global:l   { Get-ChildItem @args }
Set-Alias ls  Get-ChildItem

# head / tail
function global:head {
    param([int]$n = 10, [Parameter(ValueFromPipeline=$true, ValueFromRemainingArguments=$true)] $input)
    $input | Select-Object -First $n
}
function global:tail {
    param([int]$n = 10, [Parameter(ValueFromPipeline=$true, ValueFromRemainingArguments=$true)] $input)
    $input | Select-Object -Last $n
}

# wc — count lines, words, chars
function global:wc {
    param(
        [switch]$l, [switch]$w, [switch]$c,
        [Parameter(ValueFromPipeline=$true)] [string[]]$InputObject
    )
    begin { $lines = @() }
    process { $lines += $InputObject }
    end {
        $text = $lines -join "`n"
        $lineCount = $lines.Count
        $wordCount = ($text -split '\s+' | Where-Object { $_ }).Count
        $charCount = $text.Length
        if ($l) { return $lineCount }
        if ($w) { return $wordCount }
        if ($c) { return $charCount }
        "$lineCount $wordCount $charCount"
    }
}

# cat — output file contents, with optional line numbers
function global:cat {
    param(
        [switch]$n,
        [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
        [string[]]$Path
    )
    if ($Path) {
        foreach ($p in $Path) {
            if ($n) {
                $i = 1
                foreach ($line in [System.IO.File]::ReadLines($p)) {
                    "{0,6}`t{1}" -f $i++, $line
                }
            } else {
                Get-Content $p
            }
        }
    } else {
        $input | ForEach-Object { $_ }
    }
}

# realpath / basename / dirname
function global:realpath {
    param([Parameter(Mandatory=$true, Position=0)][string]$Path)
    (Resolve-Path $Path -ErrorAction SilentlyContinue).Path ?? [System.IO.Path]::GetFullPath($Path)
}
function global:basename {
    param([Parameter(Mandatory=$true, Position=0)][string]$Path, [string]$Suffix)
    $b = [System.IO.Path]::GetFileName($Path)
    if ($Suffix -and $b.EndsWith($Suffix)) { $b = $b.Substring(0, $b.Length - $Suffix.Length) }
    $b
}
function global:dirname {
    param([Parameter(Mandatory=$true, Position=0)][string]$Path)
    [System.IO.Path]::GetDirectoryName((Resolve-Path $Path -ErrorAction SilentlyContinue).Path ?? $Path)
}

# env — print all or a specific environment variable
function global:env {
    param([Parameter(Position=0)][string]$Name)
    if ($Name) { [System.Environment]::GetEnvironmentVariable($Name) }
    else { Get-ChildItem Env: | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" } }
}

# export — set an environment variable
function global:export {
    param([Parameter(Mandatory=$true, Position=0)][string]$Assignment)
    $k, $v = $Assignment -split '=', 2
    [System.Environment]::SetEnvironmentVariable($k.Trim(), $v)
    Set-Item -Path "Env:$($k.Trim())" -Value $v
}

# source / dot — re-run a script in the current scope
function global:source {
    param([Parameter(Mandatory=$true, Position=0)][string]$Path)
    . $Path
}
Set-Alias -Name '.' -Value source -Force -Option AllScope -ErrorAction SilentlyContinue

# man — open help page
function global:man {
    param([Parameter(Mandatory=$true, Position=0)][string]$Command)
    Get-Help $Command -Full | Out-Host -Paging
}

# time — measure command execution time
function global:time {
    param([Parameter(Mandatory=$true, Position=0, ValueFromRemainingArguments=$true)][string[]]$Cmd)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $Cmd[0] ($Cmd | Select-Object -Skip 1)
    $sw.Stop()
    Write-Host "`nreal`t$($sw.Elapsed.ToString('m\:ss\.fff'))" -ForegroundColor DarkGray
}

# kill — terminate a process by name or PID
function global:kill {
    param([Parameter(Mandatory=$true, Position=0)][string]$Target, [int]$Signal = 15)
    if ($Target -match '^\d+$') {
        Stop-Process -Id ([int]$Target) -Force -ErrorAction SilentlyContinue
    } else {
        Stop-Process -Name $Target -Force -ErrorAction SilentlyContinue
    }
}

# ps — list processes (short alias for Get-Process)
function global:psg {
    param([Parameter(Position=0)][string]$Name)
    if ($Name) { Get-Process | Where-Object { $_.Name -like "*$Name*" } }
    else { Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 }
}

# diff — compare two files
function global:diff {
    param(
        [Parameter(Mandatory=$true, Position=0)][string]$File1,
        [Parameter(Mandatory=$true, Position=1)][string]$File2
    )
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git diff --no-index -- $File1 $File2
    } else {
        Compare-Object (Get-Content $File1) (Get-Content $File2) |
            ForEach-Object { ("< ", "> ")[$_.SideIndicator -eq '=>'] + $_.InputObject }
    }
}

# history search — like Ctrl+R
function global:hgrep {
    param([Parameter(Mandatory=$true, Position=0)][string]$Pattern)
    Get-History | Where-Object { $_.CommandLine -match $Pattern } |
        Select-Object Id, CommandLine | Format-Table -AutoSize
}

# clear shorthand
Set-Alias -Name clear -Value Clear-Host -Force -ErrorAction SilentlyContinue

# tee — write to file and pass through
function global:tee {
    param(
        [Parameter(Mandatory=$true, Position=0)][string]$Path,
        [switch]$Append,
        [Parameter(ValueFromPipeline=$true)][object]$InputObject
    )
    process {
        $InputObject | Out-File -FilePath $Path -Append:$Append -Encoding utf8 -Width 9999
        $InputObject
    }
}

# md5 / sha256 shorthands
function global:md5    { param([string]$Path) Get-FileHash $Path -Algorithm MD5    | Select-Object -Expand Hash }
function global:sha256 { param([string]$Path) Get-FileHash $Path -Algorithm SHA256 | Select-Object -Expand Hash }

# ports — show listening TCP ports
function global:ports {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        Get-NetTCPConnection -State Listen |
            Select-Object LocalAddress, LocalPort, OwningProcess |
            Format-Table -AutoSize
    } else {
        netstat -an | Select-String 'LISTEN'
    }
}

# pkill — kill processes by name pattern
function global:pkill {
    param([Parameter(Mandatory=$true, Position=0)][string]$Name)
    Get-Process | Where-Object { $_.Name -like "*$Name*" } | Stop-Process -Force
}

# pgrep — find processes by name pattern
function global:pgrep {
    param([Parameter(Mandatory=$true, Position=0)][string]$Name)
    Get-Process | Where-Object { $_.Name -like "*$Name*" } |
        Select-Object Id, Name, CPU, WorkingSet | Format-Table -AutoSize
}

# du — disk usage
function global:du {
    param([Parameter(Position=0)][string]$Path = '.')
    Get-ChildItem $Path -Recurse -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum |
        ForEach-Object { "{0:N2} MB  {1}" -f ($_.Sum / 1MB), (Resolve-Path $Path) }
}

# df — disk free
function global:df {
    Get-PSDrive -PSProvider FileSystem |
        Select-Object Name,
            @{N='Used(GB)';  E={[math]::Round(($_.Used/1GB), 2)}},
            @{N='Free(GB)';  E={[math]::Round(($_.Free/1GB), 2)}},
            @{N='Total(GB)'; E={[math]::Round((($_.Used + $_.Free)/1GB), 2)}} |
        Format-Table -AutoSize
}

# chmod / chown stubs (for muscle memory on Windows)
function global:chmod {
    Write-Warning "chmod is not supported on Windows. Use 'icacls' or 'Set-Acl' instead."
}
function global:chown {
    Write-Warning "chown is not supported on Windows. Use 'icacls' or 'Set-Acl' instead."
}

# ln — create symlinks (requires admin on older Windows)
function global:ln {
    param(
        [switch]$s,
        [Parameter(Mandatory=$true, Position=0)][string]$Target,
        [Parameter(Mandatory=$true, Position=1)][string]$Link
    )
    if ($s) { New-Item -ItemType SymbolicLink -Path $Link -Target $Target -Force | Out-Null }
    else     { New-Item -ItemType HardLink     -Path $Link -Target $Target -Force | Out-Null }
}

# cp, mv, rm with -r/-f flags mapped to PowerShell equivalents
function global:cp {
    param(
        [switch]$r, [switch]$f,
        [Parameter(Mandatory=$true, Position=0)][string]$Source,
        [Parameter(Mandatory=$true, Position=1)][string]$Destination
    )
    $opts = @{ Path = $Source; Destination = $Destination }
    if ($r) { $opts['Recurse'] = $true }
    if ($f) { $opts['Force']   = $true }
    Copy-Item @opts
}
function global:mv {
    param(
        [Parameter(Mandatory=$true, Position=0)][string]$Source,
        [Parameter(Mandatory=$true, Position=1)][string]$Destination,
        [switch]$f
    )
    Move-Item -Path $Source -Destination $Destination -Force:$f
}
function global:rm {
    param(
        [switch]$r, [switch]$f,
        [Parameter(Mandatory=$true, Position=0, ValueFromRemainingArguments=$true)][string[]]$Path
    )
    foreach ($p in $Path) {
        Remove-Item -Path $p -Recurse:$r -Force:$f -ErrorAction $(if ($f) {'SilentlyContinue'} else {'Continue'})
    }
}

function prompt {
    $lastExit = $global:LASTEXITCODE
    $path = $ExecutionContext.SessionState.Path.CurrentLocation.Path -replace $global:__home_regex, "~"
    $color = if ($null -eq $lastExit -or $lastExit -eq 0) { "$([char]27)[32m" } else { "$([char]27)[31m" }
    $reset = "$([char]27)[0m"
    "$color$path$reset > "
}

function cm {
    if ($args[0] -eq "cd") {
        cd (chezmoi source-path)
    } else {
        chezmoi @args
    }
}

# Download the URL currently in the clipboard with aria2c (Windows PowerShell).
function global:dlc {
    $raw = Get-Clipboard -Raw
    $url = if ($null -eq $raw) { '' } else { $raw.Trim() }
    if (-not $url) {
        Write-Error "dlc: clipboard is empty"
        return
    }
    if ($url -notmatch '^(https?|ftp)://|magnet:') {
        Write-Error "dlc: clipboard is not a URL: $url"
        return
    }
    aria2c $url
}

if (Get-Command Set-PSReadLineOption -ErrorAction SilentlyContinue) {
    if (-not [Console]::IsOutputRedirected) {
        try {
            Set-PSReadLineOption -PredictionSource History -ErrorAction SilentlyContinue
            Set-PSReadLineOption -PredictionViewStyle Inline -ErrorAction SilentlyContinue
        }
        catch {}
    }
}