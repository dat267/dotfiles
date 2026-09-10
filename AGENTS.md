# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi Filename Conventions

`dot_` → deployed dotfile (`dot_vimrc` → `~/.vimrc`) · `private_` → mode 0600 (never remove from SSH/gitconfig) · `executable_` → executable bit, prefix stripped · `modify_` → modifies existing file on deploy · `run_once_` / `run_onchange_` → lifecycle hooks · `*.tmpl` → Go template. Prefixes stack (`private_executable_`, `executable_dot_`).

Edit source files (`dot_*` prefix), never deployed versions. Preserve `{{- ... -}}` trimming and `{{ if eq .chezmoi.os "..." }}` guards. **NEVER** wrap `%s`/`%s1` in quotes — Yazi escapes paths. No linter/formatter configs, no CI/Makefile — automation is chezmoi lifecycle hooks. Never commit secrets — use OS credential stores.

## Layout

- Shell: `dot_profile`, `private_dot_{bashrc,zshrc}`, `dot_customize_environment` (Cloud Shell)
- Editors: `dot_config/{helix,nvim,Code,zed}/`, `dot_vimrc` (nvim = zero-plugin Lua modules)
- Yazi: `dot_config/yazi/{yazi,keymap,init,theme}`
- Chezmoi: `.chezmoi.toml.tmpl` (autoAdd/autoCommit, no autoPush), `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` (zsh plugin tarballs)
- AI: `dot_config/{opencode,crush}/`, `dot_pi/`
- Python scripts: `dot_local/exact_scripts/py/` — stdlib only, see its `AGENTS.md`
- Bootstrap: `run_once_before_bootstrap-local-configs.*`, `run_onchange_after_create-{symlinks,junctions}.*`

## Commands

```bash
chezmoi diff                         # verify before applying
chezmoi apply --force <target-path>  # full apply fails on mimeapps.list TTY conflict
python3 script.py --help             # verify new CLI scripts parse
```

Chezmoi source is the authoritative reference — clone and grep it (`internal/chezmoi/` = mechanics, `internal/cmd/` = commands/template funcs):
`git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Sandbox Policy (pi)

`~/.pi/agent/extensions/sandbox` wraps every `bash` call in a kernel Landlock ruleset, inherited by the whole child process tree; `write`/`edit` tools are path-checked in-process. **Extension code must spawn processes via `bash -c …` or `gate --ws … -- <cmd>`, never raw `child_process.spawn`.**

- **Writable**: workspace (chezmoi source dir), `/tmp`, `/var/tmp`, `/dev`, `/proc`, `/sys`, `~/.cache`, `~/.npm`, `~/.cargo`, `~/go`. Everything else read-only.
- **Blocked**: `chezmoi apply` (writes boltdb + `~/.profile`/`~/.ssh/`/`~/.config/` outside allowlist — stage in workspace, give the user the exact `apply --force <path>` command); `sudo`; writes to `~/.ssh/`, `~/.config/`, `~/.local/bin/`, `~/.gnupg/`.
- **Modes** (via `/sandbox`): `workspace` (Landlock, default), `supervised` (every call confirmed), `read` (mutators removed), `yolo` (off). No Landlock (e.g. Termux) → defaults to supervised, never bricks the session.
- Tests: pure logic in `node --test` files beside sources; gate behavior via the extension's smoke test.

`.crush/` and `.omo/` are runtime dirs, not managed. `README.md`, `AGENTS.md`, `LICENSE` are in `.chezmoiignore` — never deployed.
