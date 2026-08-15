# Design: Environment-aware opencode permissions (container vs live)

Date: 2026-08-15
Status: Approved (revised — two-config approach)

## Goal

opencode behaves differently by environment: fully permissive inside the codi
sandbox container, and ask-approval-for-everything on live machines. Two
configs, each owned where it belongs.

## Background

- The repo's opencode config (`dot_config/opencode/private_opencode.json`) is
  deployed by chezmoi everywhere.
- The codi sandbox (`dot_local/scripts/py/executable_codi.py`) runs
  `chezmoi init --apply` inside the container, then writes a permissive
  `sandbox_config` to `~/.config/opencode/opencode.json` on every launch
  (`write_sandbox_config`).
- Earlier revision made the repo config a template gated on the `container`
  env var. That conflicted with codi.py's overwrite: codi.py clobbered the
  permissive template with a restrictive config on every launch. Reverted to
  the two-config approach — the template is removed.

## Approach

### Live machines (deployed by chezmoi)

`dot_config/opencode/private_opencode.json` — plain config, ask for
everything:

- `read`, `edit`, `bash`, `task`, `external_directory`, `webfetch`,
  `websearch` → `ask`
- Deny list for destructive commands: `sudo *`-adjacent dangerous commands,
  `git push --force*`, `git reset --hard*`, `git clean -f*`, `chmod -R 777*`,
  `chown -R *`, `eval *`, pipe-to-shell, and anything touching `~/.ssh`,
  `~/.aws`, `id_rsa`/`id_ed25519`/`google_compute_engine`, `.pem`, `.key`,
  `.p12`, `.pfx`, `.jks`, `credentials`.
- Sensitive file denies in `read`: `*.env`, `*.env.*`, `~/.ssh`, `~/.aws`,
  `**/*.pem`, `**/*.key`, `**/id_rsa*`, `**/*.p12`, `**/*.pfx`, `**/*.jks`,
  `**/credentials`.

### Container (written by codi.py)

`sandbox_config(workspace)` in `executable_codi.py` — fully permissive with
destructive-safety:

- `read`, `edit`, `bash`, `task`, `external_directory` → `allow`
- `external_directory` → allow all
- Deny list: `rm -rf /`, `rm -rf /*`, `shutdown*`, `reboot*`, `poweroff*`,
  `dd *`, `mkfs*`

`write_sandbox_config` still runs on every codi launch and is now correct (it
writes the permissive config that matches the container's intended behavior).

## Edge cases

- WSL / cloud shells get the live (ask-everything) config from chezmoi —
  correct, they are not the codi container.
- No env-var detection needed; the two configs are deployed/written by their
  respective owners.

## Verification

- `private_opencode.json` is valid JSON and matches the schema's
  PermissionConfig shape (all keys valid, values in enum).
- `sandbox_config()` output is valid JSON.
- `executable_codi.py` parses (python3 -m py_compile).
- In-container: `write_sandbox_config` writes the permissive config; a
  restart of opencode yields read/edit/bash/task/external_directory all
  `allow` (destructive-safety denies retained).

## Files touched

- `dot_config/opencode/private_opencode.json` (reverted from template)
- `dot_local/scripts/py/executable_codi.py` (`sandbox_config`)
