# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Repository Overview

**chezmoi**-managed dotfiles targeting Linux, Windows, and Android (Termux).

## Chezmoi Filename Conventions

| Prefix / Suffix | Meaning |
| --------------- | ------- |
| `dot_` | Deployed as a dotfile (`dot_vimrc` → `~/.vimrc`) |
| `private_` | Deployed with mode `0600` |
| `executable_` | Deployed with executable bit; prefix stripped |
| `run_once_` | Runs once on first `chezmoi apply` |
| `run_onchange_` | Runs whenever its content changes |
| `*.tmpl` | Processed as a Go template before deployment |

Prefixes can stack (`private_executable_`, `executable_dot_`).

## Key Files

| Area | Paths |
| ---- | ----- |
| Shell | `dot_profile`, `private_dot_bashrc`, `private_dot_zshrc`, `dot_local/scripts/sh/`, `dot_local/scripts/ps1/` |
| Editors | `dot_config/helix/`, `dot_vimrc`, `dot_config/nvim/` (zero-plugin, no Mason), `dot_config/Code/` |
| Yazi | `dot_config/yazi/{yazi,keymap,init,theme}` with `t f/t c` translate and `z *` tools-menu bindings |
| Media/term | `dot_config/{mpv,aria2,wezterm}/`, `dot_config/powershell/` |
| Termux | `private_dot_termux/` (Android-only) |
| Git | `private_dot_gitconfig.base`, included via `modify_private_dot_gitconfig` |
| Chezmoi | `.chezmoi.toml.tmpl`, `.chezmoiignore` |
| Bootstrap | `run_once_before_bootstrap-local-configs.*`, `run_onchange_after_create-{symlinks,junctions}.*` |

Python scripts live in `dot_local/scripts/py/`: `executable_yazi-*.py` (Yazi helpers), `executable_install_*.py` (tool installers), plus utils (`install_nerd_font`, `start-awsvpn`, `codi`, etc.), sharing `_shared.py`.

## Platform Scope

- **Linux** — primary target; bash/zsh, Neovim, Yazi, mpv, aria2, rclone, fzf
- **Windows** — PowerShell profile, VS Code settings, junction scripts
- **Android (Termux)** — `private_dot_termux/`, conditionally applied

Preserve `{{ if eq .chezmoi.os "..." }}` guards in `.tmpl` files.

## Development Guidelines

### Do
- Edit source files directly in this repo (`dot_*` prefix files, not deployed versions)
- Keep template logic minimal; preserve `{{- ... -}}` whitespace-trimming
- New Python scripts under `dot_local/scripts/py/` with appropriate `executable_` prefix
- Test with `chezmoi diff` before `chezmoi apply`
- Run `python3 script.py --help` to verify new CLI scripts parse

### Don't
- Edit files in `~/.local/share/chezmoi/` directly
- Commit secrets or machine-specific credentials — use OS credential stores, never env files or git config
- Remove `private_` prefix from sensitive files (SSH config, gitconfig)
- Break cross-platform template guards without testing on the target OS

### Python Script Patterns

- Shebang: `#!/usr/bin/env python3`
- `eprint()` for user-facing messages (stderr); `print()` for pipeline output (stdout)
- Yazi-block scripts end with `input("Press Enter to continue...")`
- Standard library only; no external dependencies
- Strip Yazi's single-quote-wrapped paths: `if len(p) >= 2 and p[0] == p[-1] and p[0] in "'\"": p = p[1:-1]`

### Neovim

Zero-plugin (built-ins only). Module load order: options, keymaps, autocmds, treesitter, netrw, statusline, brackets, comments, format, lsp. For headless testing, key gotchas, and the per-module verification checklist, see `dot_config/nvim/TESTING.md`.

### Yazi Configuration

- **NEVER wrap `%s`/`%s1` in quotes** — Yazi already escapes paths. `'nvim %s1'`, never `'nvim "%s1"'`.
- Openers (`yazi.toml`) run via keybindings; single `open` rule for Enter → xdg-open.
- Keymaps (`keymap.toml`): `%S` for batch, `--block` to show terminal output, `2>&1` to merge stderr, `z` prefix for the tools menu.
- MIME detection: Yazi native `file(1)`.

## Out of Scope

- `README.md` and `AGENTS.md` are in `.chezmoiignore` — never deployed
- `AppData/` Windows-only; `private_dot_termux/` Android-only; both ignored elsewhere
- `__pycache__/`, `*.pyc`, `*.zwc`, `*.zcompdump*` excluded from version control
