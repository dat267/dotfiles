# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi Filename Conventions

`dot_` → deployed dotfile (`dot_vimrc` → `~/.vimrc`) · `private_` → mode 0600 (never remove from SSH/gitconfig) · `executable_` → executable bit, prefix stripped · `modify_` → modifies an existing file on deploy · `run_once_` / `run_onchange_` → lifecycle hooks · `*.tmpl` → Go template. Prefixes stack (`private_executable_`, `executable_dot_`).

Edit source files (`dot_*` prefix), never deployed versions. Preserve `{{- ... -}}` trimming and `{{ if eq .chezmoi.os "..." }}` guards. Never quote `%s`/`%s1` in unix Yazi rules: Yazi escapes those paths. Windows rules quote them on purpose, see `dot_config/yazi/yazi.toml`. No linter/formatter configs, no CI/Makefile: automation is chezmoi lifecycle hooks. Never commit secrets; use OS credential stores.

## Layout

- Shell: `dot_profile`, `private_dot_{bashrc,zshrc}`
- Editors: `dot_config/{helix,nvim,Code,zed}/`, `dot_vimrc` (nvim = zero-plugin Lua modules)
- Yazi: `dot_config/yazi/{yazi,keymap,init,theme}`
- Chezmoi: `.chezmoi.toml.tmpl` (autoAdd/autoCommit, no autoPush), `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` (zsh plugin tarballs)
- AI: `dot_config/opencode/`, `dot_pi/`
- Python scripts: `dot_local/scripts/exact_py/` (stdlib only, see its `AGENTS.md`)
- Bootstrap: `run_once_before_bootstrap-local-configs.ps1.tmpl` and `run_onchange_after_create-junctions.ps1.tmpl` (Windows only); `run_onchange_after_create-symlinks.sh.tmpl` and `run_onchange_after_systemd-user-reload.sh.tmpl` (Linux)

## Commands

```bash
chezmoi diff                                 # verify before applying
chezmoi apply --force <target-path>          # targeted deploy; a full apply fails on the mimeapps.list TTY conflict
python3 script.py --help                      # verify a new CLI script parses
pi-lint-extensions.py                         # tsc --strict every pi extension; node --test does not typecheck
node --test index.test.ts                     # extension unit tests, from the extension directory
python3 -m unittest discover -s exact_tests   # Python script tests, from dot_local/scripts/exact_py/
```

Chezmoi source is the authoritative reference. Clone and grep it (`internal/chezmoi/` = mechanics, `internal/cmd/` = commands and template funcs):
`git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Sandbox (pi)

`~/.pi/agent/extensions/sandbox` wraps every `bash` call in a kernel gate; `write`/`edit` are path-checked in-process. Linux compiles `gate.c` and enforces Landlock. Other platforms have no backend and default to `yolo` with a startup warning. There is no approval mode: the agent is never asked to confirm a command.

- **Writable**: workspace (chezmoi source dir), `/tmp`, `/var/tmp`, `/dev`, `/proc`, `/sys`, `~/.cache`, `~/.npm`, `~/.cargo`, `~/go`, `~/.pi` (agent state: extension and skill deploys, settings, sessions; contains credentials, a risk the user accepted).
- **Blocked**: a full `chezmoi apply` (writes boltdb plus `~/.profile`/`~/.ssh/`/`~/.config/` outside the allowlist); `sudo`; writes to `~/.ssh/`, `~/.config/`, `~/.local/bin/`, `~/.gnupg/`. Deploy with a targeted `chezmoi apply --force <path>`. When the target is outside the writable allowlist, stage the source in the workspace and hand the user the command.
- **Modes** via `/sandbox <code>`: `RO` read-only, `WS` workspace (kernel-enforced), `RW` yolo. The code is pinned to the status line, the only surface that survives `pi -c`.

Gate interface, removed backends, extension spawn rules, and gate test coverage: `docs/sandbox.md`.

`README.md`, `AGENTS.md`, `LICENSE` are in `.chezmoiignore`: never deployed.
