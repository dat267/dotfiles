# My Dotfiles

Managed with [chezmoi](https://www.chezmoi.io/) for declarative, cross-platform dotfile management.

## Overview

This repository contains my personal dotfiles and configuration for various tools and applications. It supports **Linux**, **Windows** (PowerShell), and **Android** (Termux).

## Quick Start

```bash
# Install chezmoi
curl -sfL https://chezmoi.io/get | sh

# Initialize with this repository
chezmoi init --source=https://github.com/dat267/dotfiles

# Preview changes
chezmoi diff

# Apply changes
chezmoi apply
```

## What's Included

### Shell & Terminal
- **Bash** - Interactive shell with aliases, functions, and package manager helpers
- **PowerShell** - Cross-platform profile with OS-specific path handling
- **zsh** - Integration hints in profile

### Editors & IDEs
- **Vim** - Plugin manager (vim-plug), ale (linting), monokai theme
- **Neovim** - Lua-based configuration with lazy.nvim plugin manager
- **VS Code** - User settings and code snippets for multiple languages

### Development Tools
- **Git** - Smart aliases (`gacp`, `gsw`, `gsm`), autosquash, auto-setup remote
- **Go** - Installation script with GOPATH setup
- **Node.js** - via fnm (Fast Node Manager)
- **Python** - pyenv, virtualenv support
- **AWS CLI** - Pre-configured for `ap-east-1` region
- **Google Cloud SDK** - With bash completions and Cloud Shell SSH
- **Terraform** - Installation script

### Productivity Tools
- **lf** - Terminal file manager with archive extraction commands
- **mpv** - Media player with autoload playlist
- **aria2** - Download manager with BitTorrent configuration
- **rclone** - Cloud storage manager
- **fzf** - Fuzzy finder integration

### System Tools
- **Docker/Podman** - Rootless container engine setup via `DOCKER_HOST`

## Directory Structure

```
.
├── dot_aws/              # AWS CLI configuration
├── dot_config/           # Application configs (nvim, Code, mpv, lf, aria2)
├── dot_local/scripts/    # Installation scripts (go, fnm, terraform, etc.)
├── dot_vim/              # Vim configuration
├── dot_gitconfig         # Git configuration
├── dot_profile          # Universal shell profile
├── private_dot_bashrc    # Bash interactive configuration
├── private_dot_ssh/      # SSH configuration (private)
└── run_*.tmpl           # chezmoi automation scripts
```

## Customization

### Private Configuration

Create a `~/.local/share/chezmoi/private_dot_bashrc.local` file (symlinked to `~/.bashrc.local`) for machine-specific bash settings that won't be committed.

### Environment Variables

Create a `~/.env.local` file for private environment variables. The profile sources this if it exists.

### Custom Scripts

Personal scripts in `~/.local/scripts/{py,js,sh,ps1}` are automatically added to PATH.

## Manual Setup

Some tools require manual installation. The installation scripts are in `dot_local/scripts/sh/`:

| Script                 | Purpose           |
| ---------------------- | ----------------- |
| `install_go.sh`        | Go language setup |
| `install_fnm.sh`       | Fast Node Manager |
| `install_aws.sh`       | AWS CLI v2        |
| `install_gcloud.sh`    | Google Cloud SDK  |
| `install_terraform.sh` | Terraform         |
| `install_lf.sh`        | lf file manager   |
| `install_vscode.sh`    | VS Code           |
| `install_pwsh.sh`      | PowerShell        |

## chezmoi Automation

This repository uses chezmoi's auto-git feature to automatically commit and push changes when you run `chezmoi apply`.

## Credits

Configured by **Dat Do**.

## License

MIT