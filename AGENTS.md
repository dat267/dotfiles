# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi Filename Conventions

`dot_` → deployed dotfile (`dot_vimrc` → `~/.vimrc`) · `private_` → mode 0600 (never remove from SSH/gitconfig) · `executable_` → executable bit, prefix stripped · `modify_` → modifies an existing file on deploy · `run_once_` / `run_onchange_` → lifecycle hooks · `*.tmpl` → Go template. Prefixes stack (`private_executable_`, `executable_dot_`).

Edit source files (`dot_*` prefix), never deployed versions. Preserve `{{- ... -}}` trimming and `{{ if eq .chezmoi.os "..." }}` guards. Never quote `%s`/`%s1` in unix Yazi rules: Yazi escapes those paths. Windows rules quote them on purpose, see `dot_config/yazi/yazi.toml`. No linter/formatter configs and no Makefile: automation is chezmoi lifecycle hooks. The one CI config is `.github/workflows/windows.yml`, which exists because the Windows npm layout and `.cmd` launchers cannot be exercised on Linux — it only runs the `exact_py` test suite and the pi installer. Never commit secrets; use OS credential stores.

## Layout

- Shell: `dot_profile`, `private_dot_{bashrc,zshrc}`
- Editors: `dot_config/{helix,nvim,Code,zed}/`, `dot_vimrc` (nvim = zero-plugin Lua modules)
- Yazi: `dot_config/yazi/{yazi,keymap,init,theme}`
- Chezmoi: `.chezmoi.toml.tmpl` (autoAdd/autoCommit, no autoPush), `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` (zsh plugin tarballs)
- AI: `dot_config/opencode/`, `dot_pi/`
- Python scripts: `dot_local/scripts/exact_py/` (stdlib only, see its `AGENTS.md`)
- Bootstrap: `run_once_before_bootstrap-local-configs.ps1.tmpl` and `run_onchange_after_create-junctions.ps1.tmpl` (Windows only); `run_after_create-symlinks.sh.tmpl` (Linux/Android, idempotent repairs on every apply) and `run_onchange_after_systemd-user-reload.sh.tmpl` (Linux, tracks the service checksum)

## Commands

```bash
chezmoi diff                                 # verify before applying
chezmoi apply --force <target-path>          # targeted deploy; a full apply fails on the mimeapps.list TTY conflict
python3 script.py --help                      # verify a new CLI script parses
pi_lint_extensions.py                         # tsc --strict every pi extension; node --test does not typecheck
The Windows job runs on push (paths under `dot_local/scripts/exact_py/`, `dot_pi/`, `dot_config/powershell/`, `run_*.ps1.tmpl`) and on every PR: `gh workflow run windows` or the Actions tab. It also renders every template into a throwaway home and PowerShell-parses the profile and the two Windows run_ scripts.
node --test index.test.ts                     # extension unit tests, from the extension directory
python3 -m unittest discover -s exact_tests   # Python script tests, from dot_local/scripts/exact_py/
```

Chezmoi source is the authoritative reference. Clone and grep it (`internal/chezmoi/` = mechanics, `internal/cmd/` = commands and template funcs):
`git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Filesystem policy

There is no in-process pi sandbox or permissions extension any more, so no `/permissions` modes or status-line indicator. The kernel boundary comes from the whole-process bubblewrap launchers `pi_sandbox` (`dot_local/scripts/exact_py/executable_pi_sandbox.py`) and `pier_sandbox` (`dot_local/scripts/exact_py/executable_pier_sandbox.py`), aliased to `pi` and `pier` in `dot_profile`. Both make the root filesystem read-only and allow writes to the workspace, shared `~/.pi` agent state, caches, `~/.ssh/known_hosts`, and `/tmp`; extra writable paths persist in `~/.config/pi_sandbox/rw` or `~/.config/pier_sandbox/rw` and can also be supplied with `PI_SANDBOX_RW` or `PIER_SANDBOX_RW`. Both mask the system SSH config drop-in directory and keep `known_hosts` writable so SSH and `git push` work under the user namespace. The agent's own `bash` calls run with the account's OS permissions, so they are constrained only when the parent application was started through one of these launchers.

Deployments (`chezmoi apply`) and `sudo` are still run by the user in their own terminal, never by the agent: stage source changes in the workspace and hand over the command.

`README.md`, `AGENTS.md`, `LICENSE` are in `.chezmoiignore`: never deployed.
