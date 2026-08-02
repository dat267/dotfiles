# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Repository Overview

This is a **chezmoi**-managed dotfiles repo targeting Linux, Windows, and Android (Termux).
Chezmoi uses filename prefixes to control how files are deployed — understand them before making any edits.

## Chezmoi Filename Conventions

| Prefix / Suffix        | Meaning                                               |
| ---------------------- | ----------------------------------------------------- |
| `dot_`                 | Deployed as a dotfile (e.g. `dot_vimrc` → `~/.vimrc`) |
| `private_`             | Deployed with mode `0600` (user-only permissions)     |
| `executable_`          | Deployed with executable bit set; prefix stripped      |
| `run_once_`            | Script runs once on first `chezmoi apply`              |
| `run_onchange_`        | Script runs whenever its content changes               |
| `*.tmpl`               | Processed as a Go template before deployment           |

Prefixes can stack (e.g. `private_executable_`, `executable_dot_`).

## Key Files

### Shell & Environment
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_profile`                | Universal shell profile (bash/zsh)           |
| `private_dot_bashrc`         | Bash interactive config                      |
| `private_dot_zshrc`          | Zsh interactive config                       |
| `dot_local/scripts/sh/`      | Linux shell install scripts                  |
| `dot_local/scripts/ps1/`     | Windows PowerShell scripts                   |

### Editors
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_config/helix/`          | Helix editor config (`config.toml`)          |
| `dot_vimrc`                  | Vim config (vim-plug, ALE, monokai)          |
| `dot_config/nvim/`           | Neovim: NvChad v2.5 as lazy plugin (customizations in `lua/`); nvim-dap for debugging; Go/Python/TS LSP via Mason |
| `dot_config/Code/`           | VS Code settings                             |

### Yazi File Manager
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_config/yazi/yazi.toml`  | Openers (edit, play, open)                  |
| `dot_config/yazi/keymap.toml`| Custom: `t f/t c` translate, `z *` tools menu  |
| `dot_config/yazi/init.lua`   | Plugin setup (none currently)                |
| `dot_config/yazi/theme.toml` | Visual theme (needs Nerd Font for icons)     |
| `dot_config/yazi/plugins/`   | yazi-split (only working Lua plugin)             |

### Python Scripts (`dot_local/scripts/py/`)

**Yazi helpers** (convention: `executable_yazi-*.py`):
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `executable_yazi-translate.py` | Translate filenames or file content via web APIs |
| `executable_yazi-rename.py` | Batch rename files via `$EDITOR`             |

**Installers** (convention: `executable_install_*.py`):
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `executable_install_*.py`   | Individual tool installers (yazi, go, fnm…)  |
| `executable_uninstall_tools.py` | Removes all tools from `~/.local/bin`     |

**Other utilities:**
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `executable_install_nerd_font.py` | Install a Nerd Font (Linux/Windows)      |
| `executable_url_decode_rename.py` | Decode URL-encoded filenames in a dir      |
| `executable_start-awsvpn.py` | AWS Client VPN via SAML SSO                |
| `executable_install_android_sdk.py` | Install Android SDK cmdline-tools       |
| `executable_codi.py`            | Run opencode in an isolated podman container (Debian + latest toolchains), mounting only the current project dir |

**Shared module:**
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `_shared.py`                | COLORS/log()/get_platform_info() shared by installers |

### Other Configs
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_config/mpv/`            | MPV media player config                      |
| `dot_config/aria2/`          | aria2 download manager config                |
| `dot_config/wezterm/`        | WezTerm terminal config                      |
| `dot_config/powershell/`     | PowerShell profile                           |
| `private_dot_termux/`        | Android Termux configs                       |
| `private_dot_gitconfig`      | Git config (aliases, autosquash, etc.)       |
| `.chezmoi.toml.tmpl`         | Chezmoi config template (Git auto-push, OS paths) |
| `.chezmoiignore`             | Files excluded from deployment (OS-conditional) |
| `run_once_before_bootstrap-local-configs.*` | First-run bootstrap (local config stubs) |
| `run_onchange_after_create-symlinks.sh.tmpl` | Post-apply symlink creation (Linux) |
| `run_onchange_after_create-junctions.ps1.tmpl` | Post-apply junction creation (Windows) |

## Platform Scope

- **Linux** — primary target; bash/zsh, Neovim, Yazi, mpv, aria2, rclone, fzf
- **Windows** — PowerShell profile, VS Code settings, junction scripts
- **Android (Termux)** — `private_dot_termux/` configs, conditionally applied

Platform-specific blocks in `.tmpl` files use `{{ if eq .chezmoi.os "..." }}` guards — preserve them.

## Development Guidelines

### Do
- Edit source files directly in this repo (`dot_*` prefix files, not deployed versions)
- Keep template logic minimal and preserve `{{- ... -}}` whitespace-trimming
- Add new Python scripts under `dot_local/scripts/py/` with appropriate `executable_` prefix
- Use `executable_yazi-*` naming for all Yazi helper scripts
- Test with `chezmoi diff` before `chezmoi apply`
- Run `python3 script.py --help` to verify new CLI scripts parse correctly

### Don't
- Edit files in `~/.local/share/chezmoi/` directly
- Commit secrets or machine-specific credentials — use `~/.env.local` or `~/.gitconfig.local` (gitignored)
- Remove `private_` prefix from sensitive files (SSH config, gitconfig)
- Break cross-platform template guards without testing on the target OS

### Python Script Patterns

All executable Python scripts follow these conventions:
- Shebang: `#!/usr/bin/env python3`
- Use `eprint()` for user-facing messages (writes to stderr): `print(msg, file=sys.stderr)`
- Use `print()` for pipeline-friendly output (stdout, consumed by other tools)
- For Yazi-block scripts, end with `input("Press Enter to continue...")` to keep terminal open
- Import standard library only; avoid external dependencies
- Handle Yazi's single-quote-wrapped paths: `if len(p) >= 2 and p[0] == p[-1] and p[0] in "'\"": p = p[1:-1]`

### Yazi Configuration

- **Openers (`%s` quoting)**: NEVER wrap `%s` or `%s1` in quotes. Yazi internally escapes paths (likely single-quote wrapping). Adding extra `"` creates `"'/path/file'"` which breaks paths with spaces/special chars. Use bare `%s`, e.g. `'nvim %s1'` not `'nvim "%s1"'`.

- **Openers** (`yazi.toml`): Define scripts that run when opening files. All openers accessed via keybindings. Single `open` rule for Enter → xdg-open.
- **Keymaps** (`keymap.toml`): Bind keys to Yazi built-ins, `shell` commands, or `plugin` Lua plugins. Use `%S` for batch (all selected files). Use `--block` to show terminal output. Append `2>&1` to merge stderr into the visible output. Use `z` prefix for the tools menu (extract, compress, concat, transcode, split).
- **MIME detection**: Yazi native `file(1)` based detection.

## Out of Scope

- `README.md` is listed in `.chezmoiignore` — never deployed
- `AGENTS.md` should also be added to `.chezmoiignore`
- `AppData/` is Windows-only, ignored on other platforms
- `private_dot_termux/` is Android-only, ignored on other platforms
- `__pycache__/` and `*.pyc` are excluded from version control
- Compiled shell cache files (`*.zwc`, `*.zcompdump*`) are excluded
