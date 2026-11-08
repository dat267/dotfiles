# dotfiles

My dotfiles for **Linux**, **Windows**, and **Android (Termux)**, managed with [chezmoi](https://chezmoi.io).

## Quick start

```sh
# Linux, Android (Termux), macOS. On Termux, run `pkg install curl git` first.
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "$HOME/.local/bin" init --apply dat267
```

```powershell
# Windows (PowerShell 5.1 or later): installs chezmoi, then applies the dotfiles.
iex "&{$(irm 'https://get.chezmoi.io/ps1')} -- init --apply dat267"
```

By default both installers put the chezmoi binary in `./bin` and leave `PATH` alone. On Unix, the `-b "$HOME/.local/bin"` above installs it into a directory the deployed `~/.profile` already puts on `PATH`, so later `chezmoi apply` runs need no setup. Without `-b`, move `bin/chezmoi` there yourself.

The Windows installer always writes to `.\bin`. Move `bin\chezmoi.exe` to `$HOME\bin`, which the profile also puts on `PATH`, or install chezmoi with `winget install twpayne.chezmoi` instead. Adding the relative `.\bin` to `PATH` is not worth it.

Git is optional: chezmoi uses its built-in git when `git` is not on `PATH`.

Secrets are not in the repo. After the first apply, copy `auth.json` and any credential-store entries over by hand.

## What's included

| Category | Configs |
|---|---|
| **Shell** | Bash (`~/.bashrc`), Zsh (`~/.zshrc`, `~/.zshenv`, `~/.zprofile`), `~/.profile` |
| **Scripts** | Python helpers and tool installers in `~/.local/scripts/py` (on `PATH`) |
| **Editors** | Neovim (minimal, no plugins), Vim (vim-plug, ALE, molokai), Helix, Zed, VS Code (settings and snippets) |
| **Terminals** | WezTerm, Windows Terminal, tmux, Konsole |
| **File managers** | Yazi (Linux and Windows), lf |
| **Media** | mpv, aria2 |
| **Git** | `~/.gitconfig` (autosquash, auto-setup-remote, global identity) |
| **PowerShell** | Profile and the `Utils.psm1` module |
| **SSH** | Client config for Tailscale/CGNAT hosts |
| **AI agents** | Pi (settings, extensions, skills) and opencode (minimal config that reuses Pi's skills) |

## Platforms

`.chezmoiignore` and template guards decide what each platform gets:

- **Linux:** the primary target. Gets everything except the Windows- and Termux-only pieces, plus Konsole and systemd user units.
- **Windows:** PowerShell profile, VS Code settings, Windows Terminal, and directory junctions.
- **Android (Termux):** `~/.termux/termux.properties` and a shell config adjusted for Termux.
- **macOS:** untested. The install command works and the Linux- and Windows-only pieces are guarded out, but CI does not cover it.

## Secrets

Credentials live in the OS credential store, never in this repo:

- **Windows:** Windows Credential Manager. The PowerShell profile's `Set-ProxyCredential` stores proxy credentials there.
- **Linux and macOS:** the system secret manager or the environment.

## More

[AGENTS.md](AGENTS.md) describes the source tree and its chezmoi conventions. [ARCHITECTURE.md](ARCHITECTURE.md) explains how the pieces fit together.

## License

MIT. See [LICENSE](LICENSE).
