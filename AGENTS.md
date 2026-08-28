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
| `modify_` | Script that modifies existing file on deploy |
| `run_once_` | Runs once on first `chezmoi apply` |
| `run_onchange_` | Runs whenever its content changes |
| `*.tmpl` | Processed as a Go template before deployment |

Prefixes can stack (`private_executable_`, `executable_dot_`, `private_dot_`).

## Key Files

| Area | Paths |
| ---- | ----- |
| Shell | `dot_profile`, `private_dot_bashrc`, `private_dot_zshrc`, `dot_customize_environment` (Cloud Shell), `dot_local/scripts/sh/`, `dot_local/scripts/ps1/` |
| Editors | `dot_config/helix/`, `dot_vimrc`, `dot_vim/` (plug.vim, molokai), `dot_config/nvim/` (zero-plugin, no Mason, 10 Lua modules), `dot_config/Code/`, `dot_config/zed/` |
| Yazi | `dot_config/yazi/{yazi,keymap,init,theme}` with `t f/t c` translate and `z *` tools-menu bindings |
| Media/term | `dot_config/{mpv,aria2,wezterm}/`, `dot_config/powershell/` |
| Termux | `private_dot_termux/` (Android-only) |
| Git | `private_dot_gitconfig.base`, included via `modify_private_dot_gitconfig` |
| AI | `dot_config/opencode/` (model, LSP, permissions), `dot_config/crush/` (JSON, crushrc, context.md, skills/) |
| Chezmoi | `.chezmoi.toml.tmpl`, `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` (zsh plugin archives) |
| Dsh | `dot_config/systemd/user/dsh-web.service` (Linux-only): persistent `dsh web --no-open`; manage with `systemctl --user enable --now dsh-web`, logs via `journalctl --user -u dsh-web`; remote access via `dsht <host>` (`dot_profile`). Reload hook: `run_onchange_after_systemd-user-reload.sh.tmpl` |
| Bootstrap | `run_once_before_bootstrap-local-configs.*`, `run_onchange_after_create-{symlinks,junctions}.*` |

## Python Scripts

All under `dot_local/scripts/py/` with `executable_` prefix:

- **Yazi helpers** (10): `yazi-{translate,rename,extract,compress,ffmpeg-*}` — media ops, translations
- **Tool installers** (18): `install_{aws,bun,code,firefox,fnm,gcloud,go,lf,nerd_font,opencode,pwsh,rclone,terraform,tools,yazi,android_sdk}` — each downloads latest release to `~/.local/bin`
- **Utilities**: `codi` (Docker isolate container), `dotfiles` (rclone + git sync), `lsp` (LSP server installer), `start-awsvpn` (OpenVPN + SAML), `cloudsh` (GCP tunnel), `sysinfo`, `url_decode_rename`, `mpv`
- **Shared**: `_shared.py` — platform detection, colored logging, common helpers

See `dot_local/scripts/py/AGENTS.md` for detailed patterns.

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

### No Linter/Formatter Configs
No `.editorconfig`, `.prettierrc`, `.eslintrc`, or similar. Code style is ad-hoc. Match existing file patterns.

### No CI/Makefile
All automation is chezmoi lifecycle hooks (`run_*` scripts). No GitHub Actions, Makefile, or task runner.

### Neovim

Zero-plugin (built-ins only). Module load order: options, keymaps, autocmds, treesitter, netrw, statusline, brackets, comments, format, lsp. For headless testing reference: `dot_config/nvim/TESTING.md`.

### Yazi Configuration

- **NEVER wrap `%s`/`%s1` in quotes** — Yazi already escapes paths. `'nvim %s1'`, never `'nvim "%s1"'`.
- Openers (`yazi.toml`) run via keybindings; single `open` rule for Enter → xdg-open.
- Keymaps (`keymap.toml`): `%S` for batch, `--block` to show terminal output, `2>&1` to merge stderr, `z` prefix for the tools menu.
- MIME detection: Yazi native `file(1)`.

## Out of Scope

- `README.md` and `AGENTS.md` are in `.chezmoiignore` — never deployed
- `AppData/` Windows-only; `private_dot_termux/` Android-only; both ignored elsewhere
- `.crush/` (Crush runtime), `.omo/` (OpenAgent runtime) — not chezmoi-managed
- `__pycache__/`, `*.pyc`, `*.zwc`, `*.zcompdump*` excluded from version control