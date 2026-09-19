if ($global:__dotfiles_profile_loaded) { return }
$global:__dotfiles_profile_loaded = $true

& {
    if (-not $IsWindows) {
        $env:EDITOR = if (Get-Command nvim -ErrorAction SilentlyContinue) { 'nvim' } elseif (Get-Command vim -ErrorAction SilentlyContinue) { 'vim' } elseif (Get-Command hx -ErrorAction SilentlyContinue) { 'hx' } elseif (Get-Command helix -ErrorAction SilentlyContinue) { 'helix' } else { 'vi' }
    }

    if ($IsWindows) {
        # Windows: Get-Command enumerates PATH x PATHEXT with per-file AV
        # interception — seconds on a long dev PATH. Known install locations
        # first (no enumeration), then native where.exe as bounded fallback.
        $editor = $null
        foreach ($p in @(
                "$HOME\Apps\nvim-win64\bin\nvim.exe",
                "$env:LOCALAPPDATA\nvim\bin\nvim.exe",
                "$HOME\scoop\apps\nvim\current\nvim.exe",
                "$env:ProgramFiles\Neovim\bin\nvim.exe"
            )) {
            if (Test-Path $p) { $editor = 'nvim'; break }
        }
        if (-not $editor) {
            foreach ($name in @('nvim', 'vim', 'hx', 'helix')) {
                if (where.exe $name 2>$null) { $editor = $name; break }
                if (where.exe "$name.exe" 2>$null) { $editor = $name; break }
            }
        }
        if ($editor) { $env:EDITOR = $editor }
    }

    $paths = @(
        "$HOME/.config/powershell/scripts",
        "$HOME/.local/scripts/py",
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

    # Shared lookup for the command hooks below: resolves a bare script name to
    # a file path, honouring the `get-` prefix convention and searching the
    # current location first, then PATH. Lives outside the Windows branch so it
    # can be exercised by tests.
    function global:Get-ScriptCandidate {
        param(
            [Parameter(Mandatory = $true)][string]$CommandName,
            [string]$BasePath = $PWD.Path,
            [string[]]$PathDirs
        )
        if ($null -eq $PathDirs) { $PathDirs = $env:PATH -split [IO.Path]::PathSeparator }
        $candidates = @($CommandName)
        if ($CommandName -match '^get-(.+)$') { $candidates += $Matches[1] }
        foreach ($candidate in $candidates) {
            if ($candidate -match '[/\\]') {
                if ([System.IO.File]::Exists($candidate)) { return [System.IO.Path]::GetFullPath($candidate) }
                continue
            }
            $testPath = [System.IO.Path]::Combine($BasePath, $candidate)
            if ([System.IO.File]::Exists($testPath)) { return $testPath }
            foreach ($dir in $PathDirs) {
                if (-not [System.IO.Directory]::Exists($dir)) { continue }
                $testPath = [System.IO.Path]::Combine($dir, $candidate)
                if ([System.IO.File]::Exists($testPath)) { return $testPath }
            }
        }
        return $null
    }

    if ($IsWindows) {
        $env:GOPROXY = "https://proxy.golang.org,direct"
        $env:GOSUMDB = "off"

        # Node ignores the Windows certificate store by default, so a corporate
        # TLS-intercepting proxy breaks every Node CLI at once — npm, pi,
        # opencode, esbuild, anything that fetches over https. NODE_USE_SYSTEM_CA
        # (Node 24.6+) makes Node read the ROOT store, which is where the corp
        # CA already lands via GPO; no cafile, no bundle to keep in sync.
        # Persisted at User scope like the proxy creds below, because $env: alone
        # would only cover PowerShell sessions and miss GUI-launched apps.
        # The registry is touched only while the value is unset: once persisted,
        # startup takes the in-memory fast path and skips the read entirely.
        # Explicit values win over the default at either scope — a User-scope
        # '0' is respected, and so is a process-level export (e.g. a one-off
        # $env:NODE_USE_SYSTEM_CA='0'), which the registry read used to clobber.
        if (-not $env:NODE_USE_SYSTEM_CA) {
            $nodeCa = [Environment]::GetEnvironmentVariable('NODE_USE_SYSTEM_CA', 'User')
            if (-not $nodeCa) {
                [Environment]::SetEnvironmentVariable('NODE_USE_SYSTEM_CA', '1', 'User')
                $nodeCa = '1'
            }
            $env:NODE_USE_SYSTEM_CA = $nodeCa
        }

        # pi phones home on startup (version check + install telemetry, both to
        # pi.dev) and refreshes model catalogs over the network. PI_OFFLINE gates
        # all of it; prompting is untouched, so the network is first touched when
        # the first prompt is sent. Explicit `pi install` still works. Same
        # User-scope persistence and registry fast path as above — and the same
        # respect for an explicit value at either scope, so a process-level
        # $env:PI_OFFLINE='0' now survives startup instead of being overwritten.
        if (-not $env:PI_OFFLINE) {
            $piOffline = [Environment]::GetEnvironmentVariable('PI_OFFLINE', 'User')
            if (-not $piOffline) {
                [Environment]::SetEnvironmentVariable('PI_OFFLINE', '1', 'User')
                $piOffline = '1'
            }
            $env:PI_OFFLINE = $piOffline
        }

        # Python has no NODE_USE_SYSTEM_CA equivalent. certifi-based tools
        # (requests, pip, httpx) ship their own CA bundle and ignore the Windows
        # store, so a corp MITM root that GPO put in ROOT is invisible to them —
        # python's own ssl reads the store, but PyPI traffic goes through
        # certifi. Those tools only accept a *file*, so export the store to one.
        #
        # This is the one place where an env var REPLACES trust instead of
        # extending it (proved here with a throwaway CA: an unrelated cafile
        # makes the public registry unreachable). A partial export would
        # therefore break PyPI, which is worse than not setting this at all —
        # so the file is only installed once it is verifiably complete.
        $caPem = "$env:LOCALAPPDATA\dotfiles\windows-roots.pem"
        $caStale = -not (Test-Path $caPem)
        if (-not $caStale) { $caStale = (Get-Item $caPem).LastWriteTime -lt (Get-Date).AddDays(-30) }
        if ($caStale) {
            $sb = [System.Text.StringBuilder]::new()
            foreach ($spec in @(@('Root', 'LocalMachine'), @('CA', 'LocalMachine'), @('Root', 'CurrentUser'))) {
                $store = [System.Security.Cryptography.X509Certificates.X509Store]::new($spec[0], $spec[1])
                try {
                    $store.Open('ReadOnly')
                    foreach ($cert in $store.Certificates) {
                        [void]$sb.AppendLine("# $($cert.Subject)")
                        [void]$sb.AppendLine('-----BEGIN CERTIFICATE-----')
                        [void]$sb.AppendLine([System.Convert]::ToBase64String($cert.RawData, 'InsertLineBreaks'))
                        [void]$sb.AppendLine('-----END CERTIFICATE-----')
                    }
                } catch {
                    Write-Warning "cert export: $($spec[1])\$($spec[0]) unavailable — $($_.Exception.Message)"
                } finally {
                    $store.Close()
                }
            }
            $pem = $sb.ToString()
            # The Windows ROOT store carries the public roots alongside any corp
            # ones, so a short export means it failed.
            $certCount = ([regex]::Matches($pem, '-----BEGIN CERTIFICATE-----')).Count
            if ($certCount -ge 50 -and $pem -match 'DigiCert|ISRG Root|Baltimore') {
                New-Item -ItemType Directory -Path (Split-Path $caPem) -Force | Out-Null
                Set-Content -Path $caPem -Value $pem -Encoding ascii
            } else {
                Write-Warning "cert export produced $certCount certificates; leaving SSL_CERT_FILE alone"
                $caPem = $null
            }
        }
        if ($caPem) {
            foreach ($name in @('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'PIP_CERT')) {
                $value = [Environment]::GetEnvironmentVariable($name, 'User')
                if (-not $value) {
                    [Environment]::SetEnvironmentVariable($name, $caPem, 'User')
                    $value = $caPem
                }
                Set-Item -Path "Env:$name" -Value $value
            }
        }
        # uv reads the platform store itself; no file needed. Its own switch
        # (UV_NATIVE_TLS is deprecated in favour of this as of uv 0.11).
        $uvCerts = [Environment]::GetEnvironmentVariable('UV_SYSTEM_CERTS', 'User')
        if (-not $uvCerts) {
            [Environment]::SetEnvironmentVariable('UV_SYSTEM_CERTS', '1', 'User')
            $uvCerts = '1'
        }
        $env:UV_SYSTEM_CERTS = $uvCerts

        Set-ItemProperty -Path "HKCU:\Console" -Name "VirtualTerminalLevel" -Value 1 -Type DWord -ErrorAction SilentlyContinue

        $scriptResolvers = [ordered]@{
            '.py'  = 'python'
            '.js'  = 'node'
            '.mjs' = 'node'
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
                # git is PATH-installed on Windows; where.exe is one native call
                # (Get-Command here would re-enumerate PATH x PATHEXT with AV).
                if (where.exe git 2>$null) {
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
                $path = Get-ScriptCandidate -CommandName $commandName
                if ($path) {
                    Resolve-ScriptCommand $path $LookupArgs
                }
            }
            finally {
                $global:__in_lookup_hook = $false
            }
        }
    }

    # Utils.psm1 is a set of bash-equivalents (cat/head/wc/cp/rm/diff/ports/...)
    # that shadow working native tools elsewhere, so load it on Windows only.
    if ($IsWindows) {
        $mod = "$HOME/.config/powershell/modules"
        if ([System.IO.Directory]::Exists($mod)) {
            foreach ($f in [System.IO.Directory]::GetFiles($mod, "*.psm1")) {
                Import-Module $f -ErrorAction SilentlyContinue
            }
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

if ($IsWindows) {
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
}
if ($IsWindows) {
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
}


if ($IsWindows) {
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

# ---------------------------------------------------------------------------
# Bash-equivalent utilities — loaded from Utils.psm1
# ---------------------------------------------------------------------------

# ls and `.` are Windows-only: elsewhere the native ls is better and `source`
# (which `.` aliases) comes from Utils.psm1, which is not loaded off-Windows.
if ($IsWindows) {
    Set-Alias ls Get-ChildItem
    Set-Alias -Name '.' -Value source -Force -Option AllScope -ErrorAction SilentlyContinue
}
if (-not (Get-Command clear -ErrorAction SilentlyContinue)) {
    Set-Alias -Name clear -Value Clear-Host -Force -ErrorAction SilentlyContinue
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

if (Get-Command Set-PSReadLineOption -ErrorAction SilentlyContinue) {
    if (-not [Console]::IsOutputRedirected) {
        try {
            Set-PSReadLineOption -PredictionSource History -ErrorAction SilentlyContinue
            Set-PSReadLineOption -PredictionViewStyle Inline -ErrorAction SilentlyContinue
        }
        catch {}
    }
}