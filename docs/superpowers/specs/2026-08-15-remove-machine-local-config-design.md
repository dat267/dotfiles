# Design: Remove machine-local config mechanism (env.local / gitconfig.local)

Date: 2026-08-15
Status: Approved

## Goal

Remove the `~/.env.local` / `~/.gitconfig.local` machine-local config mechanism
entirely: delete the example templates, the bootstrap copy steps, and the
profile sourcing of `~/.env.local`. Secrets and machine-specific settings now
live in OS credential stores (Windows Credential Manager via
`Set-ProxyCredential`; Linux secret managers) rather than env files.

## Background

- `~/.env.local` was sourced by bash/zsh (`dot_profile`) and PowerShell
  (`dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`), holding
  API keys, tokens, and proxy vars in plaintext.
- `~/.gitconfig.local` was loaded via `[include]` in `private_dot_gitconfig`
  for machine-local git overrides.
- Both were created on first apply by the bootstrap scripts
  (`run_once_before_bootstrap-local-configs.*.tmpl`), which copied the example
  files into `$HOME`.
- The proxy credentials feature (2026-08-15-windows-proxy-credentials-design.md)
  already moved proxy creds to Windows Credential Manager; the proxy auth
  method now ships in the managed `private_dot_gitconfig`. Nothing in the repo
  consumes the remaining env.local variables (verified by grep).

## Changes

### Deleted files

- `dot_env.local.example`
- `dot_gitconfig.local.example`
- `run_once_before_bootstrap-local-configs.sh.tmpl` (its only content was the
  two `copy_if_missing` calls for the deleted examples)

### Modified files

- `run_once_before_bootstrap-local-configs.ps1.tmpl` — remove the
  `Copy-IfMissing` helper and both copy calls; keep the `$HOME\.vim\backup`
  directory creation and the proxy-detection hint.
- `.chezmoiignore` — remove the reference to the deleted
  `run_once_before_bootstrap-local-configs.sh.tmpl`.
- `dot_profile` — remove the `if [ -f "$HOME/.env.local" ]; then ...` block.
- `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1` —
  remove the `$envLocal` loader block; fix the comment "overriding any
  HTTP(S)_PROXY from ~/.env.local".
- `private_dot_gitconfig` — remove the `[include] path = ~/.gitconfig.local`
  section (identity is already hardcoded in this file).
- `README.md` — remove the "create machine-local configs from the example
  stubs" block and the "Machine-Specific Config" section.
- `AGENTS.md` — replace the "use `~/.env.local` or `~/.gitconfig.local`"
  guideline with a statement that secrets live in OS credential stores.

## Edge cases

- Existing `~/.env.local` / `~/.gitconfig.local` on machines become inert
  orphans (no longer sourced). They are left in place — the user may remove
  them manually.
- `.gitignore` `.env.*` rules remain (harmless; other tools may create `.env`
  files).

## Verification

- `grep -rn "env.local\|gitconfig.local"` in the repo returns nothing except
  historical docs under `docs/superpowers/` and gitignored scratch.
- `private_dot_gitconfig` parses as valid git config without the include.
- Both profile files still parse/AST-check cleanly (pwsh harness on Linux).
- Bootstrap templates render correctly for both OSes (no dangling references).

## Files touched

- Delete: `dot_env.local.example`, `dot_gitconfig.local.example`,
  `run_once_before_bootstrap-local-configs.sh.tmpl`
- Modify: `run_once_before_bootstrap-local-configs.ps1.tmpl`, `.chezmoiignore`,
  `dot_profile`, `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`,
  `private_dot_gitconfig`, `README.md`, `AGENTS.md`
