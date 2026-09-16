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
- AI: `dot_config/opencode/`, `dot_pi/`
- Python scripts: `dot_local/scripts/exact_py/` — stdlib only, see its `AGENTS.md`
- Bootstrap: `run_once_before_bootstrap-local-configs.*`, `run_onchange_after_create-{symlinks,junctions}.*`, `run_onchange_after_systemd-user-reload.sh.tmpl` (Linux)

## Commands

```bash
chezmoi diff                         # verify before applying
chezmoi apply --force <target-path>  # full apply fails on mimeapps.list TTY conflict
python3 script.py --help             # verify new CLI scripts parse
```

Chezmoi source is the authoritative reference — clone and grep it (`internal/chezmoi/` = mechanics, `internal/cmd/` = commands/template funcs):
`git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Sandbox Policy (pi)

`~/.pi/agent/extensions/sandbox` wraps every `bash` call in a sandbox gate inherited by the whole child process tree; `write`/`edit` tools are path-checked in-process. Three backends, one gate interface (`gate --ws … [--allow …] [--tmp …] -- <cmd>`): **Linux** compiles `gate.c` and applies a Landlock ruleset; **Windows** compiles `gate-win.c` to `gate.exe`, marks it Low integrity with `icacls`, and relies on Mandatory Integrity Control; **Android/Termux** compiles `gate-preload.c` twice — a launcher plus an `LD_PRELOAD` interposer (`.so`) that denies the libc write family outside the grant with EACCES. A process runs at `min(user IL, image IL)`, so `gate.exe` runs Low and its children inherit that token; a directory is writable only if it has been labelled Low `(CI)(OI)`, which the extension does recursively for the workspace and the scratch dir (`~/.cache/pi/sandbox/tmp`, which `--tmp` points `TMP`/`TEMP` at). Termux cannot run Landlock (the GKI kernel ships without it — `create_ruleset` returns ENOSYS — and unprivileged user namespaces are denied), so its interposer is the advisory tier: symlink-resolved prefix matching at the libc boundary, reads never hooked, raw syscalls bypass it, and a missing policy denies all writes (fail closed). **Extension code must spawn processes via `bash -c …` or `gate --ws … -- <cmd>`, never raw `child_process.spawn`.** Because of that wrapping, `tool_call`/`tool_result` handlers see `event.input.command` as the gate invocation (`… '--' 'bash' '-c' '<cmd>'`), never the user's command — unwrap before matching on it, or every prefix matcher silently never fires.

- **Writable**: workspace (chezmoi source dir), `/tmp`, `/var/tmp`, `/dev`, `/proc`, `/sys`, `~/.cache`, `~/.npm`, `~/.cargo`, `~/go`. Everything else read-only. On Windows the list is only the workspace plus the sandbox scratch dir, because each entry costs a recursive `icacls` pass and every labelled tree is a wider write surface.
- **Blocked**: `chezmoi apply` (writes boltdb + `~/.profile`/`~/.ssh/`/`~/.config/` outside allowlist — stage in workspace, give the user the exact `apply --force <path>` command); `sudo`; writes to `~/.ssh/`, `~/.config/`, `~/.local/bin/`, `~/.gnupg/`.
- **Modes** (via `/sandbox`): `workspace` (enforced, preferred default), `read` (mutators removed), `yolo` (off). There is no approval mode — the agent is never asked to confirm a command. With no usable backend (unsupported platform, gate compile failure, failed probe) the default is `yolo`, announced with a startup warning rather than silently, and pinned as a bare mode word on the status line — pi drops a notify issued from `session_start` when it resumes a session, so the status line is the only surface that survives `pi -c`. The Windows and Termux backends fail closed at every setup step: a missing compiler, a refused label, a compile error, or a failed round trip through the gate all yield `yolo` + warning, never a gate that runs unconfined.
- Tests: pure logic in `node --test` files beside sources. The compiled gates (`gate.c`, `gate-win.c`, `gate-preload.c`) have no automated coverage — they are verified by hand (compile + manual run); do not assume a suite exercises them.

`README.md`, `AGENTS.md`, `LICENSE` are in `.chezmoiignore` — never deployed.
