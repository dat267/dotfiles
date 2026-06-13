# My Dotfiles

Managed with [chezmoi](https://www.chezmoi.io/) for declarative, cross-platform dotfile management.

## Overview

This repository contains my personal dotfiles and configurations. It supports **Linux**, **Windows** (PowerShell), and **Android** (Termux).

## Quick Start

### Linux / macOS
```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply dat267
```

### Windows (PowerShell)
```powershell
irm get.chezmoi.io | iex; & "$env:USERPROFILE\bin\chezmoi" init --apply dat267
```

## Customization

### Private Configuration & Environment Variables

Upon first `chezmoi apply`, the bootstrap scripts automatically create template files in your home directory for machine-specific configuration:
- `~/.env.local` - For environment variables, sourced by the universal shell profile.
- `~/.gitconfig.local` - For machine-specific Git configuration (e.g. user email/name, work/personal settings).

These files are gitignored in the home directory, allowing you to safely store secrets and host-specific settings.

### Custom Scripts

- Personal scripts in `~/.local/scripts/{py,js,sh,ps1}` are automatically added to PATH.
- Installation helper scripts for developer tools and utilities (such as Go, FNM, AWS CLI, Terraform, file managers, etc.) are located in `dot_local/scripts/py/` and can be run manually to bootstrap your environment.

## chezmoi Automation

This repository uses chezmoi's git integration to automatically track configuration updates.

## License

MIT