# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi Filename Conventions

`dot_` → deployed dotfile (`dot_vimrc` → `~/.vimrc`) · `private_` → mode 0600 (never remove from SSH/gitconfig) · `executable_` → executable bit, prefix stripped · `modify_` → modifies existing file on deploy · `run_once_` / `run_onchange_` → lifecycle hooks · `*.tmpl` → Go template. Prefixes stack (`private_executable_`, `executable_dot_`).

Edit source files (`dot_*` prefix), never deployed versions. Preserve `{{- ... -}}` trimming and `{{ if eq .chezmoi.os "..." }}` guards. **NEVER** wrap `%s`/`%s1` in quotes — Yazi escapes paths. No linter/formatter configs, no CI/Makefile — automation is chezmoi lifecycle hooks. Never commit secrets — use OS credential stores.

## Layout

- Shell: `dot_profile`, `private_dot_{bashrc,zshrc}`
- Editors: `dot_config/{helix,nvim,Code,zed}/`, `dot_vimrc` (nvim = zero-plugin Lua modules)
- Yazi: `dot_config/yazi/{yazi,keymap,init,theme}`
- Chezmoi: `.chezmoi.toml.tmpl` (autoAdd/autoCommit, no autoPush), `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` (zsh plugin tarballs)
- AI: `dot_config/opencode/`, `dot_pi/`
- Python scripts: `dot_local/scripts/exact_py/` — stdlib only, see its `AGENTS.md`
- Bootstrap: `run_once_before_bootstrap-local-configs.*`, `run_onchange_after_create-{symlinks,junctions}.*`, `run_onchange_after_systemd-user-reload.sh.tmpl` (Linux)

## Commands

```bash
chezmoi diff                         # verify before applying
chezmoi apply --force <target-path>  # full apply fails on mimeapps.list TTY conflict
python3 script.py --help             # verify new CLI scripts parse
pi-lint-extensions                   # tsc --strict every pi extension; node --test does NOT typecheck — run before committing extension changes
```

Chezmoi source is the authoritative reference — clone and grep it (`internal/chezmoi/` = mechanics, `internal/cmd/` = commands/template funcs):
`git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Sandbox Policy (pi)

`~/.pi/agent/extensions/sandbox` wraps every `bash` call in a sandbox gate inherited by the whole child process tree; `write`/`edit` tools are path-checked in-process. One backend, one gate interface (`gate --ws … [--allow …] -- <cmd>`): **Linux** compiles `gate.c` and applies a Landlock ruleset — the only enforcing platform. The former Windows low-integrity (Mandatory Integrity Control + `icacls`) and Android/Termux `LD_PRELOAD` backends were removed: on those platforms the extension has no backend and defaults to `yolo` with a startup warning. **Extension code must spawn processes via `bash -c …` or `gate --ws … -- <cmd>`, never raw `child_process.spawn`.** Because of that wrapping, `tool_call`/`tool_result` handlers see `event.input.command` as the gate invocation (`… '--' 'bash' '-c' '<cmd>'`), never the user's command — unwrap before matching on it, or every prefix matcher silently never fires.

- **Writable**: workspace (chezmoi source dir), `/tmp`, `/var/tmp`, `/dev`, `/proc`, `/sys`, `~/.cache`, `~/.npm`, `~/.cargo`, `~/go`, `~/.pi` (agent state — extension/skill deploys, settings, sessions; contains credentials, a risk the user accepted). Everything else read-only.
- **Blocked**: `chezmoi apply` (writes boltdb + `~/.profile`/`~/.ssh/`/`~/.config/` outside allowlist — stage in workspace, give the user the exact `apply --force <path>` command); `sudo`; writes to `~/.ssh/`, `~/.config/`, `~/.local/bin/`, `~/.gnupg/`.
- **Modes** (via `/sandbox`): `workspace` (enforced, preferred default), `read` (mutators removed), `yolo` (off). There is no approval mode — the agent is never asked to confirm a command. With no usable backend (non-Linux platform, gate compile failure, failed probe) the default is `yolo`, announced with a startup warning rather than silently, and pinned as a bare mode word on the status line — pi drops a notify issued from `session_start` when it resumes a session, so the status line is the only surface that survives `pi -c`. A failed compile or probe yields `yolo` + warning, never a gate that runs unconfined.
- Tests: pure logic in `node --test` files beside sources. The compiled gate (`gate.c`) has no automated coverage — it is verified by hand (compile + manual run); do not assume a suite exercises it.

`README.md`, `AGENTS.md`, `LICENSE` are in `.chezmoiignore` — never deployed.
