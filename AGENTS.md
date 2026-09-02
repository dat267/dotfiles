# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi Filename Conventions

| Prefix / Suffix | Meaning |
| --------------- | ------- |
| `dot_` | Deployed as a dotfile (`dot_vimrc` → `~/.vimrc`) |
| `private_` | Deployed with mode `0600` |
| `executable_` | Deployed with executable bit; prefix stripped |
| `modify_` | Script that modifies existing file on deploy |
| `run_once_` | Runs once on first `chezmoi apply` |
| `run_onchange_` | Runs whenever its content changes |
| `*.tmpl` | Processed as a Go template before deployment |

Prefixes can stack (`private_executable_`, `executable_dot_`, `private_dot_`).

## Key Files

| Area | Paths |
| ---- | ----- |
| Shell | `dot_profile`, `private_dot_bashrc`, `private_dot_zshrc`, `dot_customize_environment` (Cloud Shell) |
| Editors | `dot_config/helix/`, `dot_vimrc`, `dot_config/nvim/` (zero-plugin Lua modules), `dot_config/Code/`, `dot_config/zed/` |
| Yazi | `dot_config/yazi/{yazi,keymap,init,theme}` |
| Chezmoi | `.chezmoi.toml.tmpl` (autoAdd/autoCommit, no autoPush), `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` (zsh plugin archives) |
| AI | `dot_config/opencode/` (bare, no plugins, managed skills), `dot_config/crush/`, `dot_pi/` |
| Dsh | `dot_config/systemd/user/dsh-web.service` (Linux-only) |
| Bootstrap | `run_once_before_bootstrap-local-configs.*`, `run_onchange_after_create-{symlinks,junctions}.*` |

## Commands

```bash
chezmoi diff          # verify before applying
chezmoi apply --force <target-path>  # full apply may fail on mimeapps.list TTY conflict
python3 script.py --help   # verify new CLI scripts parse

## Chezmoi Source

Clone the chezmoi repo to discover available features:

```sh
git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi
grep -r "feature-name" /tmp/chezmoi --include="*.go"
```

Key areas: `internal/chezmoi/` for core mechanics (source state, file attributes, templates), `internal/cmd/` for commands and template functions. The repo is the authoritative reference — AGENTS.md only documents patterns used in this dotfiles repo.
```

## Python Scripts

Scripts under `dot_local/scripts/py/` (standard library only; see its `AGENTS.md` for details).

## Conventions

- Edit source files (`dot_*` prefix), not deployed versions
- Preserve `{{- ... -}}` whitespace-trimming in templates
- Preserve `{{ if eq .chezmoi.os "..." }}` platform guards
- **NEVER** wrap `%s`/`%s1` in quotes — Yazi already escapes paths
- No linter/formatter configs — code style is ad-hoc
- No CI/Makefile — all automation is chezmoi lifecycle hooks
- Never commit secrets — use OS credential stores
- `private_` prefix means mode 0600; do not remove from sensitive files (SSH, gitconfig)

## Pi Extensions (Sandbox Policy)

`~/.pi/agent/extensions/sandbox` enforces a kernel-level Landlock ruleset that wraps every `bash` tool call. The ruleset is inherited by the whole child process tree, so nested subprocesses are covered.

### Writable paths (everything else is read-only)

| Path | Notes |
|------|-------|
| Workspace (`chezmoi source directory`) | All edits, writes, new files go here |
| `/tmp`, `/var/tmp` | Scratch files, test artifacts |
| `/dev`, `/proc`, `/sys` | Device access, process info |
| `~/.cache`, `~/.npm`, `~/.cargo` | Per-user caches |

### What the agent CANNOT do

- **`chezmoi apply`** — writes to `~/.config/chezmoi/chezmoistate.boltdb` (outside allowlist). Also writes to `~/.profile`, `~/.ssh/`, `~/.config/` — all outside the allowlist. The agent must stage changes in the workspace and give you the exact `chezmoi apply --force <target-path>` command to run.
- **`sudo`** — requires interactive password, not available in the sandbox.
- **Write to `~/.ssh/`, `~/.config/`, `~/.local/bin/`, `~/.gnupg/`** — all outside the allowlist. The agent edits source files (`dot_*` prefix), never deployed versions.

### How it works

- `write`/`edit` tools are path-checked in-process against the allowlist; bash sandboxing is enforced at the kernel.
- Any extension that spawns a process which could touch the filesystem MUST route it through `bash -c …` or `gate --ws … -- <cmd>` — never raw `child_process.spawn`.
- Modes: `workspace` (Landlock; default when available), `supervised` (every bash/write/edit call asks for confirmation), `read` (bash/write/edit removed), `yolo` (off). Switch via `/sandbox`.
- If Landlock is unavailable (e.g., Termux kernels), defaults to supervised — never brick the session.
- Tests: pure logic in `node --test` files beside sources; gate behavior is verified by the smoke test in this extension's development notes.

### Other constraints

- Full `chezmoi apply` also blocked by TTY conflict on `.config/mimeapps.list` — use `--force <target-path>` for individual paths.
- `.crush/` and `.omo/` are runtime dirs, not chezmoi-managed.
- `README.md`, `AGENTS.md`, `LICENSE` in `.chezmoiignore` — never deployed.