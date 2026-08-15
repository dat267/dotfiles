# Design: Proxy credentials via user environment variables

Date: 2026-08-15
Status: Approved

## Goal

Replace the Windows Credential Manager P/Invoke layer with user environment
variables for proxy credentials. This eliminates the ~840ms `Add-Type` C#
compile at shell startup and removes the entire P/Invoke code path, while
keeping the same helper command surface and the same proxy URL export logic.

## Background

- The profile currently stores proxy creds in Windows Credential Manager via
  P/Invoke (`Set/Get/Clear-ProxyCredential`, `Initialize-CredentialManagerType`).
- The `Add-Type` compile runs eagerly on load whenever the system proxy is
  enabled (the load path calls `Get-ProxyCredential`), costing ~840ms of C#
  compilation (Roslyn) on every fresh pwsh launch.
- User-scope environment variables (`[Environment]::Get/SetEnvironmentVariable(name, "User")`)
  are read/written in ~10ms with no P/Invoke, no compile, no external
  dependency. They persist across shells and are inherited at login.
- Security tradeoff (accepted): a user env var is plaintext — readable by any
  process running as the user, stored in registry `HKCU\Environment`. This
  reverses the earlier "no plaintext" Credential Manager decision in exchange
  for startup performance.

## Data flow (Windows only)

At shell start (unchanged callers):

1. `Test-ProxyConfig` reads the system proxy host:port from the registry
   (`HKCU:\...\Internet Settings`) — fast, no compile.
2. `Get-ProxyCredential` reads `PROXY_USERNAME` / `PROXY_PASSWORD` user env
   vars (if set).
3. `Export-ProxyEnvironment` combines registry host:port with the env creds →
   `http://user:pass@host:port`, or no-auth (`http://host:port`) when creds are
   absent.

## Helper functions (env-backed)

| Function | Behavior |
| --- | --- |
| `Set-ProxyCredential` | Prompt (via `Read-Host -AsSecureString`) for username + password; write `PROXY_USERNAME` / `PROXY_PASSWORD` as User-scope env vars. Empty password → warn, write nothing. |
| `Get-ProxyCredential` | Read both User-scope env vars; return `[pscustomobject]@{ UserName; Password }` if both present, else `$null`. |
| `Clear-ProxyCredential` | Remove both User-scope env vars (idempotent; no error if absent). |

## Deleted

- `Initialize-CredentialManagerType` (and the entire `Add-Type` C# block /
  `DotfilesCredentialManager` type).
- `$global:ProxyCredentialTarget`.
- P/Invoke calls (`CredRead`/`CredWrite`/`CredDelete`/`CredFree`),
  `Marshal` usage, `SecureStringToCoTaskMemUnicode`/`ZeroFreeCoTaskMemUnicode`.

## Kept (unchanged)

- `ConvertFrom-ProxyServer`, `ConvertTo-ProxyUrl`, `Export-ProxyEnvironment`,
  `Test-ProxyConfig` — pure URL logic and a fast registry read.
- The load-path call (`Export-ProxyEnvironment -Credential (Get-ProxyCredential)`)
  — `Get-ProxyCredential`'s return shape is unchanged (`pscustomobject` or
  `$null`).

## Error handling

- No env creds → proxy-without-auth (no `user:@host` emitted).
- Only one of the two env vars set → treated as no-auth, Write-Verbose note.
- `Set-ProxyCredential` empty password → warn, no partial write.
- `Clear-ProxyCredential` when absent → idempotent no-op.

## Verification

- New test: env-var helper round-trip (`Set` writes User-scope vars, `Get`
  reads them back, `Clear` removes them), partial-cred and no-cred cases.
- Regression: `proxy-helpers-test.ps1` (15 checks), `proxy-load-test.ps1`
  (4 checks) still pass — URL logic and load path behavior unchanged.
- Profile AST-parses.
- Manual Windows: with system proxy on + `Set-ProxyCredential`, a fresh shell
  exports `HTTP_PROXY=http://user:pass@host:port`.

## Files touched

- `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`
