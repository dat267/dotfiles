# dotfiles

Cross-platform dotfiles managed with [chezmoi](https://chezmoi.io), targeting **Linux**, **Windows**, and **Android (Termux)**.

## Quick Start

```sh
# Linux / macOS (uses git)
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply dat267
```

```powershell
# Windows (PowerShell 5.1+) — installs chezmoi, then applies the dotfiles
iex "&{$(irm 'https://get.chezmoi.io/ps1')} -- init --apply dat267"
```

The PowerShell installer places the binary in `.\bin` (it does not touch
`PATH`), so add that directory to `PATH` — or `winget install
twpayne.chezmoi` — before running further `chezmoi` commands. No system git
is required: chezmoi falls back to its built-in git when `git` is not on
`PATH`.

Secrets (`auth.json`, credential-store entries) are untracked — copy them
separately after the first apply.

## What's Included

| Category | Tools / Configs |
|---|---|
| **Shell** | Bash (`~/.bashrc`), Zsh (`~/.zshrc`), `~/.profile` |
| **Editors** | Neovim (minimal, zero-plugin), Vim (vim-plug, ALE, molokai), Helix, Zed, VS Code |
| **Terminal** | WezTerm, Windows Terminal, tmux, Konsole |
| **File Managers** | Yazi (Linux + Windows) |
| **Media** | mpv, aria2 |
| **Git** | `~/.gitconfig` (autosquash, auto-setup-remote, global identity) |
| **PowerShell** | Profile + custom `Utils.psm1` module |
| **VS Code** | Settings + snippet files across languages |
| **SSH** | Client config (Tailscale/CGNAT hosts) |
| **AI** | opencode (minimal config, shares Pi skills), Pi (agent config, extensions, skills) |

## Platform Support

Flagged by `.chezmoiignore` and `.tmpl` template guards:

- **Linux** — primary target; bash/zsh, Neovim, mpv, aria2, rclone, fzf
- **Windows** — PowerShell profile, VS Code settings, Windows Terminal, junctions, Visual Studio snippets
- **Android (Termux)** — `~/.termux/termux.properties`, platform-adjusted shell config

## Repository Layout

The source tree, its chezmoi attributes, and the per-platform guards are described in [AGENTS.md](AGENTS.md).

## Secrets

Sensitive or machine-local credentials live in OS credential stores, never in
this repo:

- **Windows** — Windows Credential Manager; proxy credentials via
  `Set-ProxyCredential` (PowerShell profile helper)
- **Linux/macOS** — your system secret manager / environment

## License

MIT — see [LICENSE](LICENSE) for details.
