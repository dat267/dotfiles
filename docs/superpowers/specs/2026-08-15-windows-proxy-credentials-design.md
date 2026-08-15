# Design: Windows proxy credentials via Credential Manager

Date: 2026-08-15
Status: Approved

## Goal

On Windows, the PowerShell profile should source proxy host/port from the
system Internet Settings and proxy credentials from Windows Credential Manager,
so proxy passwords are never stored in plaintext (`~/.env.local`, gitconfig,
or env vars on disk). Registry/Credential Manager values take precedence over
any `HTTP(S)_PROXY` already present in the environment. Helper functions are
added to set, read, and clear the stored credential. Everything must work on
PowerShell 7+.

The proxy section is removed from `~/.env.local` entirely (on all platforms);
proxy creds no longer belong in env.local anywhere.

## Background

- The profile (`dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`)
  currently loads `~/.env.local` into the environment, which may contain
  `HTTP_PROXY=http://user:password@proxy-host:8080` — a plaintext password.
- The bootstrap script (`run_once_before_bootstrap-local-configs.ps1.tmpl`)
  detects proxy enablement via the registry and hints the user to fill
  `~/.env.local`.
- The repo philosophy is zero external dependencies (stdlib-only scripts,
  no required PS modules).

## Scope of env.local removal

The proxy block is removed from `dot_env.local.example` on all platforms. The
proxy-detection hints in both bootstrap scripts are updated:

- `run_once_before_bootstrap-local-configs.ps1.tmpl` → hint points to
  `Set-ProxyCredential` instead of `~/.env.local`.
- `run_once_before_bootstrap-local-configs.sh.tmpl` (Linux) → the env.local
  proxy hint is dropped; Linux users set a proxy via `~/.gitconfig.local` or
  their own mechanism. `dot_env.local.example` no longer documents proxy vars.

## Approach

P/Invoke to the Windows Credential Manager API via `Add-Type` in the profile.
This requires no installation, and never passes the password on a command line
(unlike `cmdkey`).

## Data flow (Windows only)

1. Read `HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings`:
   `ProxyEnable`, `ProxyServer`, `ProxyOverride`.
2. If `ProxyEnable` is not `1` → set nothing (leave env as-is).
3. If enabled → build proxy URL from `ProxyServer` host:port:
   - Parse multi-scheme format (`http=proxy:8080;https=proxy2:9090`); fall back
     to bare `host:port` when no scheme prefix is present.
   - Look up credential `dotfiles:proxy` in Windows Credential Manager:
     - creds exist → `http://user:pass@host:port`
     - no creds → `http://host:port` (no auth)
4. Export `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`, `https_proxy`, and
   `NO_PROXY` (from `ProxyOverride`, converted `;` → `,`).
5. Precedence: on Windows, the registry/Credential Manager values **override**
   any existing `HTTP(S)_PROXY` environment value (including from `~/.env.local`).

## Functions

All defined in the PowerShell profile, Windows-only.

| Function | Purpose |
| --- | --- |
| `Set-ProxyCredential` | Prompt (via `Read-Host -AsSecureString`) for username + password; store via `CredWrite` under target `dotfiles:proxy` |
| `Get-ProxyCredential` | Read stored entry via `CredRead`; return object with Username + password |
| `Clear-ProxyCredential` | Remove entry via `CredDelete` |
| `Test-ProxyConfig` | Read registry proxy settings; return ProxyEnable/ProxyServer/ProxyOverride |

The fixed target name is `dotfiles:proxy`.

## Implementation notes

- One `Add-Type` block defining the `CREDENTIAL` struct and P/Invoke
  declarations for `CredRead`, `CredWrite`, `CredDelete`, `CredFree`,
  guarded so it compiles once.
- `Read-Host -AsSecureString` is available on PowerShell 7.
- The proxy block lives inside the profile's existing `if ($IsWindows)`
  branch (the profile uses the PS7 automatic `$IsWindows` variable).
- Password is built into the `http://user:pass@host:port` URL only in the
  process environment; it is never written to disk.

## Error handling

- Registry missing or `ProxyServer` empty → no proxy env vars set, no error.
- `Add-Type` compile failure → degrade to proxy-without-auth.
- Credential Manager read failure / no creds → proxy-without-auth.
- `CredWrite` failure in `Set-ProxyCredential` → clear error message.

## Verification

Headless on PowerShell 7+:
1. `Set-ProxyCredential` stores an entry; `Get-ProxyCredential` returns it;
   `Clear-ProxyCredential` removes it.
2. With `ProxyEnable=1` + stored creds, profile load exports
   `HTTP_PROXY=http://user:pass@host:port` (and HTTPS/lowercase variants).
3. With `ProxyEnable=1` and no creds, proxy exported without auth.
4. With `ProxyEnable=0`, no proxy env vars are set.
5. Profile loads without errors.
6. `dot_env.local.example` contains no proxy block; bootstrap scripts no longer
   reference proxy vars in `~/.env.local`.

## Files touched

- `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1` — P/Invoke
  block, helper functions, Windows proxy export logic
- `dot_env.local.example` — remove the Corporate / office proxy block
- `run_once_before_bootstrap-local-configs.ps1.tmpl` — hint points to
  `Set-ProxyCredential` instead of `~/.env.local`
- `run_once_before_bootstrap-local-configs.sh.tmpl` — drop the proxy hint
