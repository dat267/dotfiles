# Design: Environment-aware opencode permissions (container vs live)

Date: 2026-08-15
Status: Approved

## Goal

Make the repo's opencode config (`~/.config/opencode/opencode.json`)
environment-aware: fully permissive inside a container (with destructive-safe
denies), and ask-approval-for-everything on live machines. Detection is via
the `container` environment variable that container runtimes set.

## Background

- The current config `dot_config/opencode/private_opencode.json` is a single
  restrictive config deployed everywhere.
- The codi sandbox (`dot_local/scripts/py/executable_codi.py`) already runs
  `chezmoi init --apply` inside the container and then overwrites the opencode
  config with a permissive `sandbox_config`. This makes the repo's own config
  environment-aware so the post-apply overwrite is redundant.
- Container runtimes set `container` in the container env: podman sets
  `container=podman`, docker sets `container=docker`. Live machines have it
  unset. A chezmoi template gated on the variable being non-empty detects the
  environment correctly.

## Changes

Convert `dot_config/opencode/private_opencode.json` to
`dot_config/opencode/private_opencode.json.tmpl`, gated on
`{{ if env "container" }}`.

### In-container shape (permissive + destructive-safe)

- `read`, `edit`, `bash`, `task`, `external_directory` → `allow`
- `external_directory` → allow all
- Deny list for destructive/system commands: `rm -rf /`, `rm -rf /*`,
  `shutdown*`, `reboot*`, `poweroff*`, `dd *`, `mkfs*`

### Live shape (ask for everything + deny lists)

- `read`, `edit`, `bash`, `task`, `external_directory`, `webfetch`,
  `websearch` → `ask`
- Deny list for destructive commands (same as container, plus sensitive
  patterns): `sudo *`-adjacent dangerous commands, `git push --force*`,
  `git reset --hard*`, `git clean -f*`, `chmod -R 777*`, `chown -R *`,
  `eval *`, pipe-to-shell, and anything touching `~/.ssh`, `~/.aws`,
  `id_rsa`/`id_ed25519`/`google_compute_engine`, `.pem`, `.key`, `.p12`,
  `.pfx`, `.jks`, `credentials`.
- Sensitive file denies in `read`: `*.env`, `*.env.*`, `~/.ssh`, `~/.aws`,
  `**/*.pem`, `**/*.key`, `**/id_rsa*`, `**/*.p12`, `**/*.pfx`, `**/*.jks`,
  `**/credentials`.

## Edge cases

- Detection gates on `container` being non-empty (any runtime), not a specific
  value — robust across podman/docker.
- WSL / cloud shells have `container` unset → treated as live (ask-everything),
  matching intent.
- codi.py's `write_sandbox_config` is left as-is: it writes an equivalent
  permissive config post-apply, which is now redundant but harmless. Simplifying
  it is a separate cleanup.

## Verification

- Render the template with `chezmoi execute-template` under `container=podman`
  and with it unset; both outputs are valid JSON (python3 -m json.tool) and
  match the schema's PermissionConfig shape.
- No other repo files reference `private_opencode.json` by the old name.
- Deployed `~/.config/opencode/opencode.json` updates via `chezmoi apply`
  (then opencode restart).

## Files touched

- Rename: `dot_config/opencode/private_opencode.json` →
  `dot_config/opencode/private_opencode.json.tmpl`
