---
name: dotfiles
description: Manage chezmoi dotfiles — diff, apply, add, edit, template
user-invocable: true
---

# Dotfiles

Helps manage this chezmoi dotfiles repository.

## Instructions

When the user asks about dotfiles, use `chezmoi` commands:

- `chezmoi diff` — review pending changes
- `chezmoi apply` — apply changes to home directory
- `chezmoi add <path>` — add a file to chezmoi management
- `chezmoi edit <source-path>` — edit a source file
- `chezmoi status` — show managed files status
- `chezmoi update` — pull latest from remote and apply

Key conventions:
- `private_` prefix = `chmod 0600` (secrets)
- `executable_` prefix = executable bit
- `dot_` prefix = deployed as `.` file
- `run_once_` = runs once on first apply
- `run_onchange_` = runs when content changes
- `*.tmpl` = Go template processed before deployment

## Examples

### Check what would change
```bash
chezmoi diff
```

### Add a new file
```bash
chezmoi add ~/.config/someapp/config.toml
```

### Edit a managed file
```bash
chezmoi edit ~/.bashrc
```

### Apply changes
```bash
chezmoi apply
```