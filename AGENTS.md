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
| Editors | `dot_config/helix/`, `dot_vimrc`, `dot_config/nvim/` (zero-plugin, 10 Lua modules), `dot_config/Code/`, `dot_config/zed/` |
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
```

## Python Scripts

All 34 scripts under `dot_local/scripts/py/` (33 `executable_*.py` + `executable_mpv`). Standard library only. See `dot_local/scripts/py/AGENTS.md` for patterns.

## Conventions

- Edit source files (`dot_*` prefix), not deployed versions
- Preserve `{{- ... -}}` whitespace-trimming in templates
- Preserve `{{ if eq .chezmoi.os "..." }}` platform guards
- **NEVER** wrap `%s`/`%s1` in quotes — Yazi already escapes paths
- No linter/formatter configs — code style is ad-hoc
- No CI/Makefile — all automation is chezmoi lifecycle hooks
- Never commit secrets — use OS credential stores
- `private_` prefix means mode 0600; do not remove from sensitive files (SSH, gitconfig)

## Constraints

- Full `chezmoi apply` blocked by TTY conflict on `.config/mimeapps.list` — use `--force <target-path>` for individual paths
- `sudo` requires interactive password
- `.crush/` and `.omo/` are runtime dirs, not chezmoi-managed
- `README.md`, `AGENTS.md`, `LICENSE` in `.chezmoiignore` — never deployed