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

## What's Included

| Category | Tools / Configs |
|---|---|
| **Shell** | Bash (`~/.bashrc`), Zsh (`~/.zshrc`), `~/.profile` |
| **Editors** | Neovim (minimal, zero-plugin), Vim (vim-plug, ALE, molokai), Helix, Zed, VS Code |
| **Terminal** | WezTerm, Windows Terminal |
| **File Managers** | Yazi (Linux + Windows) |
| **Media** | mpv, aria2 |
| **Git** | `~/.gitconfig` (autosquash, aliases, per-directory identity) |
| **PowerShell** | Profile + custom `Utils.psm1` module |
| **VS Code** | Settings + 11 snippet files across languages |
| **SSH** | Client config (Tailscale/CGNAT hosts) |
| **AI** | opencode (bare config, managed skills), Crush (sandboxed, secret-blocking, skills), Pi (agent config, extensions, skills — including `workspace-sandbox`: kernel-enforced read-only outside the workspace via Landlock) |

## Platform Support

Flagged by `.chezmoiignore` and `.tmpl` template guards:

- **Linux** — primary target; bash/zsh, Neovim, mpv, aria2, rclone, fzf
- **Windows** — PowerShell profile, VS Code settings, Windows Terminal, junctions, Visual Studio snippets
- **Android (Termux)** — `~/.termux/termux.properties`, platform-adjusted shell config

## Repository Structure

```
dot_config/nvim/          Neovim minimal Lua config (fast startup, zero plugins)
dot_config/helix/         Helix editor config
dot_config/zed/           Zed editor settings
dot_config/wezterm/       WezTerm terminal config
dot_config/yazi/          Yazi file manager
dot_config/powershell/    PowerShell profile + module
dot_config/crush/         Crush config (JSON + crushrc + skills)
dot_config/opencode/      opencode config (JSON + TUI + managed skills)
dot_config/mpv/           mpv media player
dot_config/aria2/         aria2 download manager
dot_config/Code/User/     VS Code settings + 11 snippet files
dot_config/systemd/user/  Linux systemd user services (dsh-web)
dot_pi/                   Pi agent config + skills
dot_local/scripts/py/     Python utility scripts (added to PATH)
dot_local/scripts/sh/     Shell scripts
dot_local/scripts/ps1/    PowerShell scripts
dot_local/js/             JS tooling (playwright, install scripts)
AppData/Local/            Windows-only configs (Windows Terminal)
private_dot_ssh/          SSH client config
```

## Secrets

Sensitive or machine-local credentials live in OS credential stores, never in
this repo:

- **Windows** — Windows Credential Manager; proxy credentials via
  `Set-ProxyCredential` (PowerShell profile helper)
- **Linux/macOS** — your system secret manager / environment

## License

MIT — see [LICENSE](LICENSE) for details.
