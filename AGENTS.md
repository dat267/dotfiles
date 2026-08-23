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
| `dot_vimrc`                  | Vim config (vim-plug, ALE, molokai)          |
| `dot_config/nvim/`           | Neovim: zero-plugin config (built-in LSP, native treesitter, netrw, custom statusline/brackets/comments/format); no plugins or Mason |
| `dot_config/Code/`           | VS Code settings                             |

### Yazi File Manager
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_config/yazi/yazi.toml`  | Openers (edit, play, open)                  |
| `dot_config/yazi/keymap.toml`| Custom: `t f/t c` translate, `z *` tools menu  |
| `dot_config/yazi/init.lua`   | Plugin setup (none currently)                |
| `dot_config/yazi/theme.toml` | Visual theme (needs Nerd Font for icons)     |

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
| `executable_codi.py`            | Run opencode in an isolated podman container (Debian + latest toolchains), mounting only the current project dir. Toolchain installed on first launch into a persistent home volume (fnm+node LTS, uv, Go, Rust, chezmoi, opencode); survives container recreation, wiped by `codi --reset` |

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
| `private_dot_gitconfig.base`  | Git config base file (aliases, autosquash, etc.), included from `~/.gitconfig` via the `modify_private_dot_gitconfig` modify template |
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
- Commit secrets or machine-specific credentials — use OS credential stores (Windows Credential Manager, Linux secret manager), never env files or git config
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

### Neovim Configuration & Testing

The nvim config in `dot_config/nvim/` is **zero-plugin** (built-ins only: `vim.lsp`, native treesitter, netrw, custom statusline/brackets/comments/format). Modules load from `init.lua` in order: options, keymaps, autocmds, treesitter, netrw, statusline, brackets, comments, format, lsp.

**Headless testing** — logic and integration can be verified, but NOT visuals/UI:

```sh
# Config loads cleanly
nvim --headless -u ~/.config/nvim/init.lua +'lua print("ok")' +qa

# Test per-filetype LSP attach + clients
nvim --headless -u ~/.config/nvim/init.lua +'edit file.go' \
  +'lua vim.wait(800); for _,c in ipairs(vim.lsp.get_clients({bufnr=0})) do print(c.name) end' +qa
```

Key gotchas learned the hard way:
- **`nvim_input()` hangs headless** — don't use it to simulate typing. `normal! iX` inserts fine; feedkeys in insert mode often fails to dispatch callback keymaps.
- **Insert-mode keymaps/autocmds** (like `InsertCharPre` brackets, `<C-Space>` omni) can't be fully verified headless — test the decision logic directly by invoking module functions or replicating the check.
- **`nvim_feedkeys` needs `nvim_replace_termcodes("<Left>", true, false, true)`** — a literal `"<Left>"` string inserts as text, not a keypress (e.g. produced `()<Left>`).
- **Test files must be inside the workspace** (`/tmp/opencode/**` or repo) — external dirs are allowed only after confirmation, but keeping tests local avoids side effects.
- **`vim.lsp.enable` requires `filetypes` per server**; without it servers attach to every buffer. Only enable servers whose binary exists (`vim.fn.executable`), else loading a file errors/spams.
- **LSP formatting needs an attached client**: `vim.lsp.buf.format`; external formatter fallback in `lua/format.lua` uses `vim.fn.executable` to pick gofmt/rustfmt/black/prettier/shfmt/etc. and silently skips when missing.
- When testing the source config (not deployed), prepend rtp: `nvim --headless --cmd 'set rtp^=/home/dat/.local/share/chezmoi/dot_config/nvim' -u dot_config/nvim/init.lua`.

**Per-module verification checklist** (headless, each line is one check):

| Module | What to verify | Headless one-liner |
| ------ | -------------- | ------------------ |
| options | settings applied | `+'lua print(vim.o.completeopt, vim.bo.tabstop)'` |
| keymaps | mappings registered | `+'lua for _,m in ipairs(vim.api.nvim_buf_get_keymap(0,"n")) do if m.lhs=="<leader>w" then print(m.lhs) end end'` |
| autocmds | hooks exist | `+'lua print(#vim.api.nvim_get_autocmds({event="BufWritePre"}))'` |
| treesitter | parser available | `+'edit f.go' +'lua vim.treesitter.start(); print("ts ok")'` |
| netrw | options set | `+'lua print(vim.g.netrw_liststyle, vim.g.netrw_banner)'` |
| statusline | builds valid string | `+'lua print(type(require("statusline").build()) == "string")'` |
| brackets | decision logic | `+'lua ... (replicate pair/skip/backspace checks, feedkeys won't dispatch)'` |
| format | formatter chosen | `+'lua local m=require("format")'` + filetype-specific `:w` on a sample file |
| lsp | client attaches + completes | `+'edit f.go' +'lua vim.wait(800); vim.lsp.buf_request(0,"textDocument/completion",{textDocument={uri=vim.uri_from_bufnr(0)},position={0,0}},function(_,r) print(#(r and r.items or {})) end); vim.wait(1000)'` |
| lsp | diagnostics flow | `+'edit f.go' +'lua vim.wait(800); print(#vim.diagnostic.get(0))'` |

General rules: LSP checks need `vim.wait()` after load (clients attach async); invoke module functions directly rather than simulating keypresses; keep test files under `/tmp/opencode/**`.

### Yazi Configuration

- **Openers (`%s` quoting)**: NEVER wrap `%s` or `%s1` in quotes. Yazi internally escapes paths (likely single-quote wrapping). Adding extra `"` creates `"'/path/file'"` which breaks paths with spaces/special chars. Use bare `%s`, e.g. `'nvim %s1'` not `'nvim "%s1"'`.

- **Openers** (`yazi.toml`): Define scripts that run when opening files. All openers accessed via keybindings. Single `open` rule for Enter → xdg-open.
- **Keymaps** (`keymap.toml`): Bind keys to Yazi built-ins, `shell` commands, or `plugin` Lua plugins. Use `%S` for batch (all selected files). Use `--block` to show terminal output. Append `2>&1` to merge stderr into the visible output. Use `z` prefix for the tools menu (extract, compress, concat, transcode, split).
- **MIME detection**: Yazi native `file(1)` based detection.

## Out of Scope

- `README.md` is listed in `.chezmoiignore` — never deployed
- `AGENTS.md` is listed in `.chezmoiignore` — never deployed
- `AppData/` is Windows-only, ignored on other platforms
- `private_dot_termux/` is Android-only, ignored on other platforms
- `__pycache__/` and `*.pyc` are excluded from version control
- Compiled shell cache files (`*.zwc`, `*.zcompdump*`) are excluded
