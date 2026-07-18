# dotfiles

Cross-platform dotfiles managed with [chezmoi](https://chezmoi.io), targeting **Linux**, **Windows**, and **Android (Termux)**.

## Quick Start

```sh
# Linux / macOS
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply dat267
```

```powershell
# Windows
powershell -c "& { iwr -useb get.chezmoi.io | iex }; chezmoi init --apply dat267"
```

### First-run setup

After applying, create machine-local configs from the example stubs:

```sh
cp ~/.env.local.example ~/.env.local      # API keys, proxy, etc.
cp ~/.gitconfig.local.example ~/.gitconfig.local  # git identity, proxy
```

Both files are gitignored (not tracked in the repo).

## What's Included

| Category | Tools / Configs |
|---|---|
| **Shell** | Bash (`~/.bashrc`), Zsh (`~/.zshrc`), `~/.profile` |
| **Editors** | Neovim (built-in LSP for Go/JS/Lua/MD/PowerShell/Python/Rust/Sh), Vim (vim-plug, ALE, Monokai) |
| **Terminal** | WezTerm, Windows Terminal |
| **File Managers** | Yazi, lf (Linux + Windows) |
| **Media** | mpv (autoload scripts), aria2 |
| **Git** | `~/.gitconfig` (autosquash, aliases, per-directory identity) |
| **PowerShell** | Profile + custom `Utils.psm1` module |
| **VS Code** | Settings + 16 snippet files across languages |
| **SSH** | Client config (Tailscale/CGNAT hosts) |

## Platform Support

Flagged by `.chezmoiignore` and `.tmpl` template guards:

- **Linux** — primary target; bash/zsh, Neovim, lf, mpv, aria2, rclone, fzf
- **Windows** — PowerShell profile, VS Code settings, Windows Terminal, junctions
- **Android (Termux)** — `~/.termux/termux.properties`, platform-adjusted shell config

## Custom Tools (`dot_local/src/`)

| Tool | Language | Purpose |
|---|---|---|
| [audiotag](dot_local/src/audiotag/) | Go | Audio file metadata tagging |
| [keepawake](dot_local/src/keepawake/) | Go | Prevent system sleep (Linux/macOS/Windows) |

Both are auto-built by CI on every push for `linux` / `windows` / `darwin` × `amd64` / `arm64`, cross-compiled with `CGO_ENABLED=0`, and published as GitHub Release assets.

**Install all tools for the current platform:**

```sh
~/.local/scripts/py/executable_install_tools.py
```

## Repository Structure

```
dot_config/nvim/          Neovim Lua config (built-in LSP, per-language modules)
dot_config/wezterm/       WezTerm terminal config
dot_config/yazi/          Yazi file manager
dot_config/powershell/    PowerShell profile + module
dot_config/lf/            lf file manager
dot_config/mpv/           mpv media player
dot_config/aria2/         aria2 download manager
dot_config/Code/User/     VS Code settings + snippets
dot_local/src/{tool}/     Custom Go/CLI tools (built by CI)
dot_local/scripts/py/     Python utility scripts (added to PATH)
dot_local/scripts/sh/     Shell scripts
dot_local/scripts/ps1/    PowerShell scripts
AppData/Local/            Windows-only configs (lf, Windows Terminal)
private_dot_ssh/          SSH client config
```

## Machine-Specific Config

Sensitive or machine-local settings use these files (never committed):

- `~/.env.local` — API keys, proxy vars, cloud tokens (sourced by both bash/zsh and PowerShell)
- `~/.gitconfig.local` — Git identity override, proxy — loaded via `[include]` in `~/.gitconfig`

## License

MIT — see [LICENSE](LICENSE) for details.
