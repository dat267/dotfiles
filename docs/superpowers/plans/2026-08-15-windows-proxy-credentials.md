# Windows Proxy Credentials via Credential Manager — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Windows, source proxy host/port from the system Internet Settings and proxy credentials from Windows Credential Manager via P/Invoke, so proxy passwords are never stored in plaintext; add `Set-ProxyCredential` / `Get-ProxyCredential` / `Clear-ProxyCredential` / `Test-ProxyConfig` helpers; remove the proxy block from `~/.env.local` entirely.

**Architecture:** Self-contained PowerShell in the profile. One guarded `Add-Type` block defines the `CREDENTIAL` struct + `CredRead`/`CredWrite`/`CredDelete`/`CredFree` P/Invoke. Pure helper functions (`ConvertFrom-ProxyServer`, `ConvertTo-ProxyUrl`, `Export-ProxyEnvironment`) parse registry `ProxyServer` and build proxy URLs, so the credential plumbing is isolated from the URL logic and testable on Linux. On profile load (Windows only), after `~/.env.local` is sourced, the proxy env vars are exported from registry + Credential Manager, overriding anything from env.local.

**Tech Stack:** Windows PowerShell 5.1 + PowerShell 7+ (profile must work on both), `Add-Type` P/Invoke to `advapi32.dll`, registry `HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings`.

## Global Constraints

- Profile must parse and load on both Windows PowerShell 5.1 and PowerShell 7+ (P/Invoke marshaling identical on both; `Read-Host -AsSecureString` available on PS 5.1).
- Zero external dependencies — no PSGallery modules, no `cmdkey` on the command line.
- Fixed credential target name: `dotfiles:proxy`.
- Registry/Credential Manager proxy values override any pre-existing `HTTP(S)_PROXY` env vars on Windows.
- Proxy password is built into `http://user:pass@host:port` only in the process environment; never written to disk.
- `~/.env.local` proxy block removed on ALL platforms; both bootstrap hints updated.
- Tests run with pwsh (present in this workspace at `/tmp/opencode/pwsh`, invoked as `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh`); test scripts live in `.cache/pwsh/` (gitignored). Credential Manager runtime behavior (Set/Get/Clear round-trip) requires Windows and is documented as manual verification.

---

### Task 1: Remove proxy from env.local and update bootstrap hints

**Files:**
- Modify: `/home/opencode/projects/cd6aabd59c160be5/dot_env.local.example` (remove lines 5-13, the Corporate / office proxy block)
- Modify: `/home/opencode/projects/cd6aabd59c160be5/run_once_before_bootstrap-local-configs.ps1.tmpl` (line 17-20: hint points to `Set-ProxyCredential`)
- Modify: `/home/opencode/projects/cd6aabd59c160be5/run_once_before_bootstrap-local-configs.sh.tmpl` (lines 7-9: drop the proxy hint)
- Modify: `/home/opencode/projects/cd6aabd59c160be5/README.md` (line 72: drop "proxy vars" from the `.env.local` description)

**Interfaces:**
- Consumes: nothing.
- Produces: `dot_env.local.example` with no proxy block; bootstrap scripts that no longer reference proxy vars in `~/.env.local`; README no longer lists proxy vars under `.env.local`.

- [ ] **Step 1: Write the failing check**

```bash
grep -n "HTTP_PROXY\|HTTPS_PROXY\|proxy vars\|proxy-host" \
  /home/opencode/projects/cd6aabd59c160be5/dot_env.local.example \
  /home/opencode/projects/cd6aabd59c160be5/run_once_before_bootstrap-local-configs.ps1.tmpl \
  /home/opencode/projects/cd6aabd59c160be5/run_once_before_bootstrap-local-configs.sh.tmpl \
  /home/opencode/projects/cd6aabd59c160be5/README.md
```

Expected: matches exist (RED).

- [ ] **Step 2: Edit `dot_env.local.example`**

Delete lines 5-13 (from `# ---------------------------------------------------------------------------` above "Corporate / office proxy" through the `NO_PROXY=` line), so the file starts the "API keys / tokens" section after the header:

```
# ~/.env.local — machine-specific environment variables
# Sourced by ~/.profile (bash/zsh) and the PowerShell profile at login.
# NOT tracked in git. Copy from ~/.env.local.example and fill in values.

# ---------------------------------------------------------------------------
# API keys / tokens  (never commit these)
# ---------------------------------------------------------------------------
```

- [ ] **Step 3: Edit `run_once_before_bootstrap-local-configs.ps1.tmpl`**

Replace lines 17-20:

```powershell
$proxyEnabled = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue).ProxyEnable
if ($proxyEnabled -eq 1) {
    Write-Host "Proxy detected — uncomment and fill proxy vars in ~/.env.local" -ForegroundColor Yellow
}
```

with:

```powershell
$proxyEnabled = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue).ProxyEnable
if ($proxyEnabled -eq 1) {
    Write-Host "System proxy detected — run Set-ProxyCredential to store proxy credentials in Windows Credential Manager" -ForegroundColor Yellow
}
```

- [ ] **Step 4: Edit `run_once_before_bootstrap-local-configs.sh.tmpl`**

Delete lines 7-9 (the `if [ -n "${HTTP_PROXY:-}..."` block and its echo), leaving the `copy_if_missing` calls as the last statements before `{{ end -}}`.

- [ ] **Step 5: Edit `README.md` line 72**

Change:

```markdown
- `~/.env.local` — API keys, proxy vars, cloud tokens (sourced by both bash/zsh and PowerShell)
```

to:

```markdown
- `~/.env.local` — API keys, cloud tokens (sourced by both bash/zsh and PowerShell)
```

- [ ] **Step 6: Run the check to verify it passes**

```bash
grep -n "HTTP_PROXY\|HTTPS_PROXY\|proxy vars\|proxy-host" \
  /home/opencode/projects/cd6aabd59c160be5/dot_env.local.example \
  /home/opencode/projects/cd6aabd59c160be5/run_once_before_bootstrap-local-configs.ps1.tmpl \
  /home/opencode/projects/cd6aabd59c160be5/run_once_before_bootstrap-local-configs.sh.tmpl \
  /home/opencode/projects/cd6aabd59c160be5/README.md; echo "grep exit: $?"
```

Expected: no matches, `grep exit: 1` (GREEN).

- [ ] **Step 7: Commit**

```bash
git add dot_env.local.example run_once_before_bootstrap-local-configs.ps1.tmpl run_once_before_bootstrap-local-configs.sh.tmpl README.md
git commit -m "chore: remove proxy block from env.local; update bootstrap hints"
```

---

### Task 2: Add pure proxy config helpers with tests

**Files:**
- Modify: `/home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1` (insert helper functions inside the Windows proxy section)
- Test: `/home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-helpers-test.ps1` (create)

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces:
  - `ConvertFrom-ProxyServer([string]$ProxyServer) -> hashtable` — maps scheme→host:port. Bare `host:port` maps to both `http` and `https`; `http=a;https=b` parses per scheme; empty/blank → `@{}`.
  - `ConvertTo-ProxyUrl([string]$HostPort, [string]$UserName, [string]$Password) -> string|null` — `http://host:port` with optional `user:pass`; `$HostPort` empty → `$null`. Username/password URL-escaped via `[uri]::EscapeDataString`.
  - `Export-ProxyEnvironment([string]$ProxyServer, [string]$ProxyOverride, $Credential) -> void` — sets `HTTP_PROXY`/`HTTPS_PROXY`/`http_proxy`/`https_proxy` from parsed schemes, `NO_PROXY`/`no_proxy` from `ProxyOverride` (`;` → `,`). `$Credential` may be `$null` (no auth). Uses `Set-Item -Path "Env:..."`.
  - These are non-global (scoped inside the init block); the export call and tests use them within the same scope.

- [ ] **Step 1: Write the failing test**

Create `/home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-helpers-test.ps1`:

```powershell
param([string]$ProfilePath)
$ErrorActionPreference = "Stop"

$script:failures = 0
$script:checks = 0
function Assert($cond, $msg) {
    $script:checks++
    if (-not $cond) { $script:failures++; Write-Output "  FAIL: $msg" }
    else { Write-Output "  ok:   $msg" }
}

# ---- Extract the pure helpers from the profile source ----
$content = Get-Content -Raw $ProfilePath
function Extract-Function([string]$name) {
    $start = $content.IndexOf("function $name")
    if ($start -lt 0) { throw "function $name not found" }
    $openBrace = $content.IndexOf("{", $start)
    $depth = 0
    $i = $openBrace
    for (; $i -lt $content.Length; $i++) {
        if ($content[$i] -eq '{') { $depth++ }
        elseif ($content[$i] -eq '}') { $depth-- }
        if ($depth -eq 0) { break }
    }
    return $content.Substring($start, $i - $start + 1)
}
Invoke-Expression (Extract-Function "ConvertFrom-ProxyServer")
Invoke-Expression (Extract-Function "ConvertTo-ProxyUrl")
Invoke-Expression (Extract-Function "Export-ProxyEnvironment")

Write-Output "== ConvertFrom-ProxyServer =="
Assert ((ConvertFrom-ProxyServer 'proxy.corp:8080')['http'] -eq 'proxy.corp:8080') "bare host:port -> http"
Assert ((ConvertFrom-ProxyServer 'proxy.corp:8080')['https'] -eq 'proxy.corp:8080') "bare host:port -> https"
$multi = ConvertFrom-ProxyServer 'http=proxy.corp:8080;https=proxy-sec:9090'
Assert ($multi['http'] -eq 'proxy.corp:8080') "multi-scheme -> http part"
Assert ($multi['https'] -eq 'proxy-sec:9090') "multi-scheme -> https part"
Assert ((ConvertFrom-ProxyServer '') .Count -eq 0) "empty string -> empty map"

Write-Output "== ConvertTo-ProxyUrl =="
Assert ((ConvertTo-ProxyUrl 'proxy.corp:8080' $null $null) -eq 'http://proxy.corp:8080') "no auth"
Assert ((ConvertTo-ProxyUrl 'proxy.corp:8080' 'user' 'pass') -eq 'http://user:pass@proxy.corp:8080') "with auth"
Assert ((ConvertTo-ProxyUrl '' $null $null) -eq $null) "empty host -> null"

Write-Output "== Export-ProxyEnvironment =="
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:http_proxy,Env:https_proxy,Env:NO_PROXY,Env:no_proxy -ErrorAction SilentlyContinue
Export-ProxyEnvironment 'http=proxy.corp:8080' 'localhost;<local>' ([pscustomobject]@{ UserName='u'; Password='p' })
Assert ($env:HTTP_PROXY -eq 'http://u:p@proxy.corp:8080') "HTTP_PROXY with auth"
Assert ($env:HTTPS_PROXY -eq $null) "HTTPS_PROXY unset when no https scheme"
Assert ($env:NO_PROXY -eq 'localhost,<local>') "NO_PROXY ; -> ,"
Assert ($env:no_proxy -eq 'localhost,<local>') "no_proxy lowercase set"

Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:http_proxy,Env:https_proxy,Env:NO_PROXY,Env:no_proxy -ErrorAction SilentlyContinue
Export-ProxyEnvironment 'proxy.corp:8080' $null $null
Assert ($env:HTTP_PROXY -eq 'http://proxy.corp:8080') "no creds -> no auth"
Assert ($env:https_proxy -eq 'http://proxy.corp:8080') "bare host:port applies to https"

Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:http_proxy,Env:https_proxy,Env:NO_PROXY,Env:no_proxy -ErrorAction SilentlyContinue
Export-ProxyEnvironment '' $null $null
Assert ($null -eq $env:HTTP_PROXY) "empty ProxyServer -> nothing set"

Write-Output ""
Write-Output "SUMMARY: $($script:checks) checks, $($script:failures) failures"
if ($script:failures -gt 0) { exit 1 }
```

- [ ] **Step 2: Run test to verify it fails**

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-helpers-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: FAIL with `function ConvertFrom-ProxyServer not found` (helpers don't exist yet).

- [ ] **Step 3: Add the proxy section with pure helpers to the profile**

Inside the profile, immediately before the final `$global:__home_regex = [regex]::Escape($HOME)` line (line 221), insert (the full section — pure helpers here, P/Invoke + credential functions + export wiring come in Tasks 3-4):

```powershell
    if ($IsWindows) {
        # --- Proxy credentials (Windows Credential Manager) ---

        # Parse HKCU Internet Settings ProxyServer into scheme -> host:port.
        # Handles "http=a:8080;https=b:9090" and bare "host:port".
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

        # Export HTTP(S)_PROXY / http(s)_proxy / NO_PROXY / no_proxy from
        # registry values. $Credential may be $null (proxy without auth).
        function Export-ProxyEnvironment {
            param([string]$ProxyServer, [string]$ProxyOverride, $Credential)
            $schemes = ConvertFrom-ProxyServer $ProxyServer
            foreach ($name in 'http', 'https') {
                $hp = $schemes[$name]
                if ($hp) {
                    $url = ConvertTo-ProxyUrl -HostPort $hp -UserName $Credential.UserName -Password $Credential.Password
                    Set-Item -Path "Env:${name}_PROXY" -Value $url
                    Set-Item -Path "Env:${name}_proxy" -Value $url
                }
            }
            if ($ProxyOverride) {
                $noProxy = $ProxyOverride -replace ';', ','
                Set-Item -Path 'Env:NO_PROXY' -Value $noProxy
                Set-Item -Path 'Env:no_proxy' -Value $noProxy
            }
        }

        # --- End proxy credentials (pure helpers) ---
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-helpers-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: `SUMMARY: 13 checks, 0 failures` (GREEN).

- [ ] **Step 5: Commit**

```bash
git add dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
git commit -m "feat(powershell): add pure proxy config helpers"
```

---

### Task 3: Add Credential Manager P/Invoke + Set/Get/Clear functions

**Files:**
- Modify: `/home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1` (extend the Windows proxy section)
- Test: `/home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-cred-test.ps1` (create)

**Interfaces:**
- Consumes: the `if ($IsWindows)` proxy section added in Task 2.
- Produces:
  - `Add-Type` type `DotfilesCredentialManager` (class with `CREDENTIAL` struct + static `CredRead`, `CredWrite`, `CredDelete`, `CredFree`) — guarded so it compiles once.
  - `global:Set-ProxyCredential` — prompts (if params omitted) via `Read-Host` / `Read-Host -AsSecureString`, writes via `CredWrite` under `dotfiles:proxy`, frees blob.
  - `global:Get-ProxyCredential` — reads via `CredRead`, returns `[pscustomobject]@{ UserName; Password }` or `$null`.
  - `global:Clear-ProxyCredential` — `CredDelete`; prints confirmation.
  - `global:Test-ProxyConfig` — returns `[pscustomobject]@{ ProxyEnable; ProxyServer; ProxyOverride }` from the registry.
  - `$global:ProxyCredentialTarget = 'dotfiles:proxy'`.

- [ ] **Step 1: Write the failing test**

Create `/home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-cred-test.ps1`:

```powershell
param([string]$ProfilePath)
$ErrorActionPreference = "Stop"

$script:failures = 0
$script:checks = 0
function Assert($cond, $msg) {
    $script:checks++
    if (-not $cond) { $script:failures++; Write-Output "  FAIL: $msg" }
    else { Write-Output "  ok:   $msg" }
}

# ---- Extract the whole proxy section and execute it ----
# The section starts at the "# --- Proxy credentials" marker and ends at the
# "# --- End proxy credentials" marker.
$content = Get-Content -Raw $ProfilePath
$start = $content.IndexOf("# --- Proxy credentials")
$end = $content.IndexOf("# --- End proxy credentials")
if ($start -lt 0 -or $end -lt 0) { throw "proxy section markers not found" }
$end = $content.IndexOf("`n", $end) + 1
$section = $content.Substring($start, $end - $start)

# Wrap so the functions land in script scope (section is a bare block).
$section = "function global:__ProxySection_Entry { $section }" 
# The section is an `if ($IsWindows) { ... }` — force it true for extraction.
$section = $section.Replace('if ($IsWindows) {', 'if ($true) {')
Invoke-Expression $section
# __ProxySection_Entry runs the if-block but defines global: functions inside.
& __ProxySection_Entry

Assert (('DotfilesCredentialManager' -as [type]) -ne $null) "Add-Type compiled DotfilesCredentialManager"
Assert ((Get-Command Set-ProxyCredential -ErrorAction SilentlyContinue) -ne $null) "Set-ProxyCredential defined"
Assert ((Get-Command Get-ProxyCredential -ErrorAction SilentlyContinue) -ne $null) "Get-ProxyCredential defined"
Assert ((Get-Command Clear-ProxyCredential -ErrorAction SilentlyContinue) -ne $null) "Clear-ProxyCredential defined"
Assert ((Get-Command Test-ProxyConfig -ErrorAction SilentlyContinue) -ne $null) "Test-ProxyConfig defined"
Assert ($global:ProxyCredentialTarget -eq 'dotfiles:proxy') "target name is dotfiles:proxy"

Write-Output ""
Write-Output "SUMMARY: $($script:checks) checks, $($script:failures) failures"
if ($script:failures -gt 0) { exit 1 }
```

Note: `CredRead`/`CredWrite` runtime round-trip requires Windows (advapi32.dll). On Linux the P/Invoke type still compiles; the manual Windows verification in Step 5 covers the round-trip.

- [ ] **Step 2: Run test to verify it fails**

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-cred-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: FAIL — `proxy section markers not found` or `DotfilesCredentialManager` type missing (P/Invoke not added yet).

- [ ] **Step 3: Add the P/Invoke block + credential functions to the profile**

Replace the trailing `# --- End proxy credentials (pure helpers) ---` line inside the proxy section with the full section ending (P/Invoke + credential functions + the markers used by the test):

```powershell
        if (-not ('DotfilesCredentialManager' -as [type])) {
            Add-Type @"
using System;
using System.Runtime.InteropServices;

public class DotfilesCredentialManager {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL {
        public uint Flags;
        public uint Type;
        public string TargetName;
        public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredRead(string target, uint type, uint flags, out IntPtr credential);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredWrite(ref CREDENTIAL credential, uint flags);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredDelete(string target, uint type, uint flags);

    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern void CredFree(IntPtr buffer);
}
"@
        }

        $global:ProxyCredentialTarget = 'dotfiles:proxy'

        function global:Set-ProxyCredential {
            [CmdletBinding()]
            param(
                [string]$UserName,
                [securestring]$Password
            )
            if (-not $UserName) { $UserName = Read-Host 'Proxy username' }
            if (-not $Password) { $Password = Read-Host 'Proxy password' -AsSecureString }

            $ptr = [IntPtr]::Zero
            try {
                $cred = New-Object DotfilesCredentialManager+CREDENTIAL
                $cred.Type = 1
                $cred.TargetName = $global:ProxyCredentialTarget
                $cred.UserName = $UserName
                $ptr = [Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($Password)
                $cred.CredentialBlobSize = $Password.Length * 2
                $cred.CredentialBlob = $ptr
                $cred.Persist = 2
                if (-not [DotfilesCredentialManager]::CredWrite([ref]$cred, 0)) {
                    throw "CredWrite failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
                }
                Write-Host "Proxy credential saved."
            } finally {
                if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeCoTaskMemUnicode($ptr) }
            }
        }

        function global:Get-ProxyCredential {
            $ptr = [IntPtr]::Zero
            if (-not [DotfilesCredentialManager]::CredRead($global:ProxyCredentialTarget, 1, 0, [ref]$ptr)) {
                return $null
            }
            try {
                $cred = [Runtime.InteropServices.Marshal]::PtrToStructure($ptr, [type][DotfilesCredentialManager+CREDENTIAL])
                $size = [int]$cred.CredentialBlobSize
                $bytes = New-Object byte[] $size
                [Runtime.InteropServices.Marshal]::Copy($cred.CredentialBlob, $bytes, 0, $size)
                $password = [System.Text.Encoding]::Unicode.GetString($bytes)
                return [pscustomobject]@{ UserName = $cred.UserName; Password = $password }
            } finally {
                [DotfilesCredentialManager]::CredFree($ptr)
            }
        }

        function global:Clear-ProxyCredential {
            if ([DotfilesCredentialManager]::CredDelete($global:ProxyCredentialTarget, 1, 0)) {
                Write-Host 'Proxy credential removed.'
            } else {
                Write-Warning "Clear-ProxyCredential: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
            }
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-cred-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: `SUMMARY: 6 checks, 0 failures` (GREEN). The `& __ProxySection_Entry` run may print a benign `HKCU:` drive-not-found error on Linux — if so, confirm it is non-terminating (the test still passes); if it aborts, wrap the `Test-ProxyConfig` call in the extraction wrapper with a try/catch in the test (not the profile).

- [ ] **Step 5: Manual Windows verification (documented, not automated)**

On a Windows machine with the profile deployed, verify the round-trip once:

```powershell
Set-ProxyCredential                 # prompt for user/pass
Get-ProxyCredential                 # returns UserName + Password
Clear-ProxyCredential               # removes entry
Get-ProxyCredential                 # returns $null after clear
```

- [ ] **Step 6: Commit**

```bash
git add dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
git commit -m "feat(powershell): Credential Manager P/Invoke + proxy credential functions"
```

---

### Task 4: Wire proxy export into profile init + regression

**Files:**
- Modify: `/home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1` (add the export call at the end of the proxy section)
- Test: `/home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-load-test.ps1` (create)

**Interfaces:**
- Consumes: `Test-ProxyConfig`, `Get-ProxyCredential`, `Export-ProxyEnvironment` from Tasks 2-3.
- Produces: on profile load (Windows, `ProxyEnable=1`), `HTTP_PROXY`/`HTTPS_PROXY`/`http_proxy`/`https_proxy`/`NO_PROXY`/`no_proxy` set from registry + Credential Manager, overriding env.local values.

- [ ] **Step 1: Write the failing test**

Create `/home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-load-test.ps1`:

```powershell
param([string]$ProfilePath)
$ErrorActionPreference = "Stop"

$script:failures = 0
$script:checks = 0
function Assert($cond, $msg) {
    $script:checks++
    if (-not $cond) { $script:failures++; Write-Output "  FAIL: $msg" }
    else { Write-Output "  ok:   $msg" }
}

# Extract full proxy section and run it with $IsWindows forced true.
$content = Get-Content -Raw $ProfilePath
$start = $content.IndexOf("# --- Proxy credentials")
$end = $content.IndexOf("# --- End proxy credentials")
if ($start -lt 0 -or $end -lt 0) { throw "proxy section markers not found" }
$end = $content.IndexOf("`n", $end) + 1
$section = $content.Substring($start, $end - $start)

# Stub registry + credential manager so the export wiring is testable on Linux.
function global:Test-ProxyConfig {
    [pscustomobject]@{ ProxyEnable = 1; ProxyServer = 'http=proxy.corp:8080;https=proxy-sec:9090'; ProxyOverride = 'localhost;<local>' }
}
function global:Get-ProxyCredential {
    [pscustomobject]@{ UserName = 'alice'; Password = 's3cret' }
}

# Clear pre-existing proxy vars, then run the section's export wiring.
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:http_proxy,Env:https_proxy,Env:NO_PROXY,Env:no_proxy -ErrorAction SilentlyContinue
$env:HTTP_PROXY = 'http://old:value@nowhere:1'   # simulate a stale env.local value

# Run the full section with the "export wiring" part. It is inside the
# `if ($IsWindows) {` block at the end of the section; force true.
$section = $section.Replace('if ($IsWindows) {', 'if ($true) {')
$section = "function global:__ProxySection_Run { $section }"
Invoke-Expression $section
& __ProxySection_Run

Assert ($env:HTTP_PROXY -eq 'http://alice:s3cret@proxy.corp:8080') "HTTP_PROXY overridden with creds"
Assert ($env:https_proxy -eq 'http://alice:s3cret@proxy-sec:9090') "https_proxy set from https scheme"
Assert ($env:NO_PROXY -eq 'localhost,<local>') "NO_PROXY exported"
Assert ($env:no_proxy -eq 'localhost,<local>') "no_proxy lowercase exported"

Write-Output ""
Write-Output "SUMMARY: $($script:checks) checks, $($script:failures) failures"
if ($script:failures -gt 0) { exit 1 }
```

- [ ] **Step 2: Run test to verify it fails**

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-load-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: FAIL — `HTTP_PROXY` still equals the stale value (no export wiring yet), or the section markers/function not found.

- [ ] **Step 3: Add the export wiring to the profile**

Immediately before the `# --- End proxy credentials ---` marker (inside the `if ($IsWindows)` block), add:

```powershell
        # Export proxy env vars from registry + Credential Manager on load,
        # overriding any HTTP(S)_PROXY from ~/.env.local.
        try {
            $proxyCfg = Test-ProxyConfig
            if ($proxyCfg.ProxyEnable -eq 1 -and $proxyCfg.ProxyServer) {
                Export-ProxyEnvironment -ProxyServer $proxyCfg.ProxyServer -ProxyOverride $proxyCfg.ProxyOverride -Credential (Get-ProxyCredential)
            }
        } catch {
            Write-Verbose "Proxy setup skipped: $($_.Exception.Message)"
        }

        # --- End proxy credentials ---
```

- [ ] **Step 4: Run test to verify it passes**

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-load-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: `SUMMARY: 4 checks, 0 failures` (GREEN).

- [ ] **Step 5: Full-profile syntax + load regression on Linux**

```bash
# AST parse check (strips template guards; profile is not a template, plain parse):
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -Command '
$tokens=$null;$errors=$null
[System.Management.Automation.Language.Parser]::ParseFile("/home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1",[ref]$tokens,[ref]$errors)|Out-Null
if($errors.Count){$errors|ForEach-Object{Write-Output $_.Message};exit 1}else{Write-Output "PARSE OK"}'
```

Expected: `PARSE OK`.

Then re-run Tasks 2-3 tests to confirm no regression:

```bash
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-helpers-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /tmp/opencode/pwsh -NoProfile -File /home/opencode/projects/cd6aabd59c160be5/.cache/pwsh/proxy-cred-test.ps1 -ProfilePath /home/opencode/projects/cd6aabd59c160be5/dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
```

Expected: both `0 failures`.

- [ ] **Step 6: Manual Windows verification (documented)**

With the profile deployed on Windows:
1. `Set-ProxyCredential` → enter user/pass.
2. Restart PowerShell (proxy is exported at profile load). `echo $env:HTTPS_PROXY` shows `http://user:pass@host:port`.
3. Set `HKCU:\...\Internet Settings` `ProxyEnable=0` → restart → no proxy env vars.
4. `Clear-ProxyCredential` → restart → proxy exported without auth.

- [ ] **Step 7: Commit**

```bash
git add dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1
git commit -m "feat(powershell): export proxy env from registry + Credential Manager at load"
```

---

## Self-Review Notes

- **Spec coverage:** Goal (CM creds, no plaintext) — Tasks 2-4; helpers Set/Get/Clear/Test-ProxyConfig — Task 3; registry precedence over env.local — Task 4 (export overrides via Set-Item after env.local is sourced); remove proxy from env.local entirely + bootstrap hints — Task 1; PS5/PS7 parity — Global Constraints + P/Invoke + `Read-Host -AsSecureString`; fixed target `dotfiles:proxy` — Task 3; proxy-without-auth fallback — Task 2 `ConvertTo-ProxyUrl` no-cred path + Task 4 wiring.
- **Placeholder scan:** all steps contain concrete code and expected output.
- **Type consistency:** `ConvertFrom-ProxyServer`, `ConvertTo-ProxyUrl`, `Export-ProxyEnvironment`, `Test-ProxyConfig`, `Get-ProxyCredential`, `Set-ProxyCredential`, `Clear-ProxyCredential`, `$global:ProxyCredentialTarget` names and signatures match across Tasks 2-4 and their tests.
