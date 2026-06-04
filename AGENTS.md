# AGENTS.md

Guidelines for AI agents (Copilot, Antigravity, Cursor, etc.) working in this dotfiles repository.

## Repository Overview

This is a **chezmoi**-managed dotfiles repo targeting Linux, Windows (PowerShell), and Android (Termux).
Chezmoi uses filename prefixes to control how files are deployed — understand them before making any edits.

## Chezmoi Filename Conventions

| Prefix / Suffix        | Meaning                                               |
| ---------------------- | ----------------------------------------------------- |
| `dot_`                 | Deployed as a dotfile (e.g. `dot_vimrc` → `~/.vimrc`) |
| `private_`             | Deployed with mode `0600` (user-only permissions)     |
| `run_once_`            | Script runs once on first `chezmoi apply`             |
| `run_onchange_`        | Script runs whenever its content changes              |
| `*.tmpl`               | Processed as a Go template before deployment          |

## Key Files

| File                                         | Purpose                                        |
| -------------------------------------------- | ---------------------------------------------- |
| `.chezmoi.toml.tmpl`                         | Chezmoi config template (Git auto-push, OS paths) |
| `.chezmoiignore`                             | Files excluded from deployment (OS-conditional) |
| `dot_profile`                                | Universal shell profile (sourced by bash/zsh)  |
| `private_dot_bashrc`                         | Bash interactive config                        |
| `private_dot_zshrc`                          | Zsh interactive config                         |
| `private_dot_gitconfig`                      | Git config (aliases, autosquash, etc.)         |
| `dot_vimrc`                                  | Vim config (vim-plug, ALE, monokai)            |
| `dot_config/nvim/`                           | Neovim Lua config (lazy.nvim)                  |
| `dot_config/powershell/`                     | PowerShell profile                             |
| `dot_config/wezterm/`                        | WezTerm terminal config                        |
| `dot_config/yazi/`                           | Yazi file manager config                       |
| `dot_local/`                                 | Local scripts and installation helpers         |
| `dot_local/src/{tool}/`                      | Source for custom compiled tools (any language) |
| `dot_local/src/{tool}/Makefile`              | **Required** build contract (see Custom Tools) |
| `.github/workflows/build-tools.yml`          | CI: auto-discovers tools, builds & releases    |
| `run_once_before_bootstrap-local-configs.*`  | First-run bootstrap (local config stubs)       |
| `run_onchange_after_create-symlinks.sh.tmpl` | Post-apply symlink creation (Linux)            |
| `run_onchange_after_create-junctions.ps1.tmpl` | Post-apply junction creation (Windows)       |

## Platform Scope

- **Linux** — primary target; bash/zsh, Neovim, lf, mpv, aria2, rclone, fzf
- **Windows** — PowerShell profile, VS Code settings, AppData configs, junction scripts
- **Android (Termux)** — `private_dot_termux/` configs, conditionally applied

Platform-specific blocks in `.tmpl` files use `{{ if eq .chezmoi.os "..." }}` guards — preserve them.

## Development Guidelines

### Do
- Use `chezmoi edit <file>` or edit source files directly in this repo
- Keep template logic minimal and well-commented
- Preserve existing `{{- ... -}}` whitespace-trimming in templates
- Add new install scripts under `dot_local/scripts/sh/` (Linux) or `dot_local/scripts/ps1/` (Windows)
- Test changes with `chezmoi diff` before `chezmoi apply`

### Don't
- Edit files in `~/.local/share/chezmoi/` directly — edit the source repo instead
- Commit secrets or machine-specific credentials — use `~/.env.local` or `~/.gitconfig.local` (gitignored)
- Remove `private_` prefix from sensitive files (SSH config, gitconfig)
- Break cross-platform template guards without testing on the target OS

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
~/.local/scripts/py/install_max.py    # downloads all tools for current platform
~/.local/scripts/py/uninstall_max.py  # removes them from ~/.local/bin
```

Both scripts auto-detect available tools from the latest GitHub Release assets — no config needed.

## Out of Scope

- `README.md` is listed in `.chezmoiignore` — it is never deployed to target machines
- `AGENTS.md` should also be added to `.chezmoiignore` to prevent deployment
- `AppData/` is Windows-only and ignored on other platforms
- `private_dot_termux/` is Android-only and ignored on other platforms
