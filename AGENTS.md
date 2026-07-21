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
| `create_`              | Created if absent on target; never updated             |
| `modify_`              | Applied on top of existing files                       |
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
| `dot_vimrc`                  | Vim config (vim-plug, ALE, monokai)          |
| `dot_config/nvim/`           | Neovim Lua config (lazy.nvim)                |
| `dot_config/Code/`           | VS Code settings                             |

### Yazi File Manager
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_config/yazi/yazi.toml`  | Openers (edit, extract, concat, transcode, compress) |
| `dot_config/yazi/keymap.toml`| Custom keybindings (`.`, `e`, `O`, `R`, `x`, `C`, `T`, `v`, `tf`, `tc`) |
| `dot_config/yazi/init.lua`   | Plugin setup (none currently)                |
| `dot_config/yazi/theme.toml` | Visual theme                                 |
| `dot_config/yazi/plugins/`   | Custom plugins (none currently)              |

### Python Scripts (`dot_local/scripts/py/`)

**Yazi helpers** (convention: `executable_yazi-*.py`):
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `executable_yazi-translate.py` | Translate filenames or file content via web APIs |
| `executable_yazi-rename.py` | Batch rename files via `$EDITOR`             |
| `executable_yazi-compress.py` | Compress selected files (7z/zip)            |
| `executable_yazi-extract.py` | Extract archives interactively               |
| `executable_yazi-ffmpeg-concat.py` | Concatenate media files                |
| `executable_yazi-ffmpeg-transcode.py` | Transcode media files              |

**Installers** (convention: `executable_install_*.py`):
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `executable_install_tools.py` | Downloads all tools from GitHub Releases    |
| `executable_install_*.py`   | Individual tool installers (yazi, go, fnm…)  |
| `executable_uninstall_tools.py` | Removes all tools from `~/.local/bin`     |

**Other utilities:**
| Script                      | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `executable_url_decode_rename.py` | Decode URL-encoded filenames in a dir  |
| `executable_build_tools.py` | CI build script for custom compiled tools    |
| `common.py`                 | Shared utility module (no shebang)           |

### Other Configs
| File                         | Purpose                                      |
| ---------------------------- | -------------------------------------------- |
| `dot_config/mpv/`            | MPV media player config                      |
| `dot_config/aria2/`          | aria2 download manager config                |
| `dot_config/lf/`             | lf file manager (lightweight fallback, no MIME) |
| `dot_config/wezterm/`        | WezTerm terminal config                      |
| `dot_config/powershell/`     | PowerShell profile                           |
| `private_dot_termux/`        | Android Termux configs                       |
| `private_dot_gitconfig`      | Git config (aliases, autosquash, etc.)       |
| `.chezmoi.toml.tmpl`         | Chezmoi config template (Git auto-push, OS paths) |
| `.chezmoiignore`             | Files excluded from deployment (OS-conditional) |
| `.github/workflows/build-tools.yml` | CI: auto-discovers tools, builds & releases |
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

- **Openers** (`yazi.toml`): Define scripts that run when opening files. All openers accessed via keybindings. Single `open` rule for Enter → xdg-open.
- **Keymaps** (`keymap.toml`): Bind keys to Yazi built-ins or `shell` commands. Use `%S` for batch (all selected files). Use `--block` to show terminal output. Append `2>&1` to merge stderr into the visible output.
- **MIME detection** (Yazi built-in): Uses `file(1)` for content-based MIME detection.

## Custom Tools (`dot_local/src/`)

Each subdirectory under `dot_local/src/` containing a `Makefile` is auto-discovered by CI and built for all supported platforms.

### Adding a New Tool

1. Create `dot_local/src/{toolname}/` with your source code
2. Add a `Makefile` implementing the build contract below
3. Push to `main` — CI does the rest (no config files to edit)

### Makefile Build Contract

CI calls your Makefile as:
```sh
make -C dot_local/src/{tool} build OUT=/absolute/path/to/binary
```

With these environment variables set:

| Variable      | Example value               | Meaning                          |
| ------------- | --------------------------- | -------------------------------- |
| `GOOS`        | `linux`, `windows`          | Target OS                        |
| `GOARCH`      | `amd64`, `arm64`            | Target architecture              |
| `VERSION`     | `tools/20260604-032500`     | Release tag (embed if desired)   |
| `OUT`         | `/abs/path/tool-linux-amd64`| Where to write the binary        |
| `CGO_ENABLED` | `0`                         | Always disabled                  |

Your `Makefile` **must** write an executable to `$(OUT)`. Language examples:

**Go:**
```makefile
build:
	go build -ldflags="-s -w -X main.version=$(VERSION)" -o "$(OUT)" .
```

**Rust:**
```makefile
build:
	cargo build --release --target $(RUST_TARGET)
	cp target/$(RUST_TARGET)/release/$(BINARY) "$(OUT)"
```

**Python (PyInstaller):**
```makefile
build:
	pyinstaller --onefile --distpath "$(dir $(OUT))" --name "$(notdir $(OUT))" main.py
```

### Supported Platforms

| `GOOS`    | `GOARCH`         |
| --------- | ---------------- |
| `linux`   | `amd64`, `arm64` |
| `windows` | `amd64`          |

### Install / Uninstall

```sh
~/.local/scripts/py/install_tools.py      # downloads all tools for current platform
~/.local/scripts/py/uninstall_tools.py    # removes them from ~/.local/bin
```

Both scripts auto-detect available tools from the latest GitHub Release assets — no config needed.

## Out of Scope

- `README.md` is listed in `.chezmoiignore` — never deployed
- `AGENTS.md` should also be added to `.chezmoiignore`
- `AppData/` is Windows-only, ignored on other platforms
- `private_dot_termux/` is Android-only, ignored on other platforms
- `__pycache__/` and `*.pyc` are excluded from version control
- Compiled shell cache files (`*.zwc`, `*.zcompdump*`) are excluded
