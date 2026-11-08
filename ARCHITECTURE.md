# Architecture

This repository is a chezmoi source tree. chezmoi reads each path's name and attributes and turns it into a file, a directory, or a lifecycle action in the home directory. [AGENTS.md](AGENTS.md) covers the naming conventions and everyday commands; this document covers the major components and how they fit together.

## From source to home directory

- **Filename prefixes** (`dot_`, `private_`, `executable_`, `modify_`, `exact_`) set the target path, file mode, merge behavior, and whether a directory is exact. [AGENTS.md](AGENTS.md) lists them.
- **Templates** (`*.tmpl`) are Go templates that fill in platform-specific values and guard platform-specific content.
- **`.chezmoiignore`** decides which sources apply on each OS, and keeps documentation, runtime state, and generated files out of the managed set.
- **Hooks** (`run_once_`, `run_onchange_`, `run_`) handle bootstrap and post-deploy work that a static file cannot express. Templates and `.chezmoiignore` gate them by platform.
- **`.chezmoi.toml.tmpl`** configures chezmoi itself. When git is available, it turns on auto-add and auto-commit of source edits and leaves pushing manual.

Linux, Windows, and Android (Termux) share most of the configuration. Templates and ignore rules isolate what is OS-specific. A Windows CI workflow covers the Windows npm installs and command launchers, which cannot be tested on Linux.

## Components

### Shell and desktop

`dot_profile`, the shell rc files, and the editor, terminal, and application configs make up the interactive environment. `dot_local/scripts/` puts helper commands on `PATH`. Its `exact_py/` subtree deploys to `~/.local/scripts/py/` and holds standard-library-only Python tools with `unittest` coverage.

### Pi and opencode

`dot_pi/private_agent/` holds Pi's settings, themes, extensions, and skills. Extensions deploy to `~/.pi/agent/extensions/` and skills to `~/.pi/agent/skills/`, which opencode's config also points at.

Two files merge into Pi's own state instead of replacing it, so settings Pi or the user wrote survive:

- `modify_settings.json` merges the managed settings into `settings.json`.
- `modify_private_models.json` merges into `models.json` a 500k `contextWindow` cap for every model whose catalog advertises 1M tokens or more.

The `system` theme is the default; `flat` is installed as an option.

### Sandboxed launchers

`pi_sandbox` and `pier_sandbox` are Python launchers that share their policy and argument handling through `_sandbox.py`. The shell aliases `pix` and `piex` run them, while the bare `pi` and `pier` commands stay unsandboxed. In sandboxed modes, bubblewrap is the process boundary: the root filesystem is read-only, only a short list of paths is writable, and host IPC endpoints are masked. [AGENTS.md](AGENTS.md) states the policy invariants, and `dot_local/scripts/exact_py/AGENTS.md` covers the implementation.

### Lifecycle hooks

On Linux and Android, a hook repairs the VS Code `Code/User` symlink on every apply. On Linux, another reloads the systemd user manager when the service unit changes. On Windows, hooks bootstrap local configuration once and recreate junctions. They are kept apart from ordinary file rendering so each can be idempotent or run only on change.

## Verification

Python script tests live in `dot_local/scripts/exact_py/exact_tests/`. Pi extensions have their own Node tests and are typechecked by `pi_lint_extensions.py`. The Windows workflow also renders the templates and parses the PowerShell scripts. [AGENTS.md](AGENTS.md) lists the commands and the order to run them in.

## What is not source

Credentials and machine-local runtime state are not configuration. Secrets belong in OS credential stores, and chezmoi ignores generated files, package artifacts, caches, and opencode's runtime state.

Open work is in [TODO.md](TODO.md).
