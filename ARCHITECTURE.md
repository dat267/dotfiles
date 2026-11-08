# Architecture

This repository is a declarative chezmoi source tree. Files are transformed from repository paths and attributes into files, directories, and lifecycle actions in a user's home directory. Chezmoi naming conventions and day-to-day editing commands live in [AGENTS.md](AGENTS.md); this document describes the major components and how they fit together.

## Source-to-home deployment

- Filename prefixes (`dot_`, `private_`, `executable_`, `modify_`, `exact_`) encode target paths, modes, merge behavior, and directory exactness; [AGENTS.md](AGENTS.md) lists them.
- `*.tmpl` files use Go templates for platform-specific values and guards. `.chezmoiignore` selects which sources apply on each OS and excludes documentation, runtime state, and generated artifacts.
- `run_once_`, `run_onchange_`, and `run_` scripts handle bootstrap or post-deployment work that cannot be expressed as static files. Hooks are platform-gated through `.chezmoiignore` and templates.
- `.chezmoi.toml.tmpl` configures chezmoi behavior. When Git is available it enables source auto-add and auto-commit, while leaving pushes manual.

The main target platforms are Linux, Windows, and Android through Termux. Most configuration is shared; templates and ignore rules isolate OS-specific files and actions. The Windows-only workflow exercises Windows npm installation and command launchers that cannot be tested on Linux.

## Main components

### Shell and desktop configuration

`dot_profile`, shell rc files, editor and terminal configuration, and application settings provide the user's interactive environment. `dot_local/scripts/` places helper commands on `PATH`; its `exact_py/` subtree is deployed as `~/.local/scripts/py/` and contains standard-library-only Python utilities with `unittest` coverage.

### Pi and opencode

`dot_pi/private_agent/` supplies Pi settings, themes, extensions, and skills. Extensions are deployed to `~/.pi/agent/extensions/`; skills are deployed to `~/.pi/agent/skills/` and can also be referenced by opencode's configuration. `modify_settings.json` merges the managed Pi settings into the existing settings file, preserving unrelated user settings. The `system` theme remains the default and `flat` is an optional theme.

### Sandboxed launchers

The `pi_sandbox` and `pier_sandbox` Python entry points share policy and argument handling through `_sandbox.py`. Shell aliases `pix` and `piex` invoke these launchers; the bare `pi` and `pier` commands remain unsandboxed. In sandboxed modes, bubblewrap supplies the process boundary: the root filesystem is read-only, a limited set of writable paths is exposed, and host IPC endpoints are masked. The policy invariants are in [AGENTS.md](AGENTS.md); implementation detail is in `dot_local/scripts/exact_py/AGENTS.md`.

### Lifecycle integration

Linux and Android hooks repair the VS Code `Code/User` symlink and reload systemd user units when their service definition changes. Windows hooks bootstrap local configuration and recreate junctions. These operations are deliberately separate from ordinary managed-file rendering so they can be idempotent or change-triggered.

## Verification and ownership

Python script tests live in `dot_local/scripts/exact_py/exact_tests/`. Pi extensions have local Node tests and are checked with `pi_lint_extensions.py`; the Windows workflow additionally renders templates and parses Windows PowerShell scripts. The relevant commands and ordering constraints are in [AGENTS.md](AGENTS.md).

Credentials and machine-local runtime state are not source configuration. Secrets belong in OS credential stores; generated files, package artifacts, caches, and opencode runtime state are excluded from chezmoi management.

See [TODO.md](TODO.md) for current open work.
