# Design: Wire Scoop proxy to system proxy for PowerShell 7

Date: 2026-08-15
Status: Superseded — removed 2026-08-15 (startup cost)

> This feature was removed. The scoop proxy sync ran `scoop config` as a child
> process on every PowerShell profile load, adding real startup latency. The
> proxy env-var export (Credential Manager) remains; scoop's own proxy can be
> configured once manually via `scoop config proxy currentuser@default`.

## Goal

When the Windows system proxy is enabled, Scoop should use it with the
current user's Windows credentials (`currentuser@default`). The scoop proxy
config is applied on every PowerShell 7 profile load, with no password
written to disk. When the system proxy is disabled, a stale scoop proxy
setting is removed.

## Background

- The shared profile (`dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`)
  already sources proxy host/port from system Internet Settings and proxy
  credentials from Windows Credential Manager, exporting `HTTP(S)_PROXY` env
  vars (see `2026-08-15-windows-proxy-credentials-design.md`).
- Scoop has no first-class proxy env-var integration for authentication;
  it reads `scoop config proxy`, which persists in scoop's config.json.
- Scoop's `currentuser` token uses the current logged-in Windows user's
  credentials (integrated auth — no password needed); `default` resolves to
  the Internet Options proxy (the same registry values the profile reads).
- The shared profile is sourced via a stub at
  `$docsDir\PowerShell\Microsoft.PowerShell_profile.ps1` (PowerShell 7).

## Data flow (Windows only)

In the shared profile's existing `if ($IsWindows)` proxy block:

1. If `ProxyEnable -eq 1` (system proxy on) and `Get-Command scoop` succeeds:
   run `scoop config proxy currentuser@default`.
2. If `ProxyEnable -ne 1` (system proxy off) and scoop exists:
   run `scoop config rm proxy` to clear any stale setting.
3. Failures from `scoop config` are swallowed by the block's existing
   try/catch; proxy env-var export is unaffected.

## Implementation notes

- `currentuser@default` embeds no password; nothing secret is written to
  scoop's config.json or anywhere on disk.
- Gate the scoop config on `ProxyEnable -eq 1` alone (not `$ProxyServer`),
  since `default` resolves the host:port at scoop call time.
- The profile uses the PS7 automatic `$IsWindows` variable.
- `Get-Command scoop -ErrorAction SilentlyContinue` guards the scoop call.

## Error handling

- scoop not installed → skip silently, no error.
- system proxy disabled → `scoop config rm proxy` (only if scoop present).
- `scoop config` failure → caught by existing try/catch; degrade quietly.
- `scoop config` rewrites config.json each shell start — cheap, keeps scoop
  in sync with registry proxy changes.

## Verification

Headless on PowerShell 7+:
1. Profile AST-parses — verified via the repo's pwsh parse-check harness
   on Linux.
2. `junction-test.ps1` regression passes (20 checks); the `$profiles`
   array contains the PS7 path only.

Manual on Windows (documented, not automated):
1. With system proxy on, a new PowerShell session leaves
   `scoop config proxy` returning `currentuser@default`.
2. `scoop search` / `scoop install` route through the proxy.
3. With system proxy off, `scoop config proxy` is empty/removed.

## Files touched

- `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`
- `run_onchange_after_create-junctions.ps1.tmpl`
