# Design: Proxy credentials via user environment variables

Date: 2026-08-15
Status: Approved (revised — store full URLs in HTTP_PROXY/HTTPS_PROXY)

## Goal

Replace the Windows Credential Manager P/Invoke layer with user environment
variables. `Set-ProxyCredential` builds the full proxy URL
(`http://user:pass@host:port`) from the registry host:port + prompted creds and
stores it directly in USER-scope `HTTP_PROXY` / `HTTPS_PROXY` / `http_proxy` /
`https_proxy`. At login the vars are inherited, so the profile does **zero**
proxy work at startup. This eliminates the ~840ms `Add-Type` C# compile and
the entire P/Invoke code path.

## Background

- The profile previously stored proxy creds in Windows Credential Manager via
  P/Invoke, costing ~840ms of C# (Roslyn) compile on every fresh pwsh launch.
- User-scope env vars are read/written in ~10ms with no P/Invoke, no compile.
  They persist across shells and are inherited into the process env at login.
- Security tradeoff (accepted): a user env var is plaintext — readable by any
  process running as the user, stored in registry `HKCU\Environment`. This
  reverses the earlier "no plaintext" Credential Manager decision in exchange
  for startup performance.

## Data flow

At login: `HTTP_PROXY`/`HTTPS_PROXY`/`http_proxy`/`https_proxy` are already in
the process environment (inherited from User scope). The profile does nothing
proxy-related at load.

## Helper functions

| Function | Behavior |
| --- | --- |
| `Set-ProxyCredential` | Prompt (via `Read-Host -AsSecureString`) for username + password; read registry `ProxyServer` for host:port; build `http://user:pass@host:port`; write to User-scope `HTTP_PROXY`/`HTTPS_PROXY`/`http_proxy`/`https_proxy` and the current process env. Empty password → warn, write nothing. |
| `Get-ProxyCredential` | Return the stored `HTTP_PROXY` value (or `$null`). |
| `Clear-ProxyCredential` | Remove all four proxy env vars at User scope and from the current process. |

## Deleted

- `Initialize-CredentialManagerType` and the entire `Add-Type` C# block /
  `DotfilesCredentialManager` type.
- `$global:ProxyCredentialTarget`, all P/Invoke calls, `Marshal` usage.
- The load-path proxy export block (`Test-ProxyConfig` + `Export-ProxyEnvironment`
  call) and the now-unused `Export-ProxyEnvironment` / `ConvertFrom-ProxyServer`
  functions.

## Kept

- `Test-ProxyConfig` (registry read) — used by `Set-ProxyCredential` to get
  host:port.
- `ConvertTo-ProxyUrl` — used by `Set-ProxyCredential` to build the URL.

## Error handling

- No registry `ProxyServer` → `Set-ProxyCredential` warns and aborts (can't
  build a URL without host:port).
- `Set-ProxyCredential` empty password → warn, no write.
- `Clear-ProxyCredential` when absent → idempotent no-op.

## Verification

- New test: `Set-ProxyCredential` with a stubbed registry host:port writes all
  four env vars with the correct URL; `Get-ProxyCredential` returns it;
  `Clear-ProxyCredential` removes them; empty-password aborts.
- Regression: `proxy-helpers-test.ps1` updated for the removed functions.
- Profile AST-parses; no `DotfilesCredentialManager` type anywhere.

## Files touched

- `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`

