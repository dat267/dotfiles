# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi Filename Conventions

`dot_` → deployed dotfile (`dot_vimrc` → `~/.vimrc`) · `private_` → mode 0600 (never remove from SSH/gitconfig) · `executable_` → executable bit, prefix stripped · `modify_` → merges into an existing file at deploy, never a full replacement · `exact_` → directory contents are exact, unmanaged files removed on apply · `run_once_` / `run_onchange_` → lifecycle hooks · `*.tmpl` → Go template. Prefixes stack (`private_executable_`, `executable_dot_`).

Edit chezmoi source files, never deployed targets. Preserve `{{- ... -}}` trimming and `{{ if eq .chezmoi.os "..." }}` guards. In Yazi rules, never quote `%s`/`%s1` in unix rules (Yazi escapes those paths); Windows rules quote them on purpose, see `dot_config/yazi/yazi.toml`.

## Layout

Notable source → deployed mappings:

| Source | Deployed |
|---|---|
| `dot_local/scripts/exact_py/` | `~/.local/scripts/py/` (on `PATH`) |
| `dot_pi/agent/exact_extensions/` | `~/.pi/agent/extensions/` |
| `dot_pi/agent/exact_skills/` | `~/.pi/agent/skills/` |
| `dot_pi/agent/private_APPEND_SYSTEM.md` | `~/.pi/agent/APPEND_SYSTEM.md` (mode 0600) |
| `dot_pi/agent/modify_settings.json` | `~/.pi/agent/settings.json` (merged) |
| `dot_config/opencode/private_opencode.json` | `~/.config/opencode/opencode.json` |

```
dot_profile               Shell env for bash/zsh (PATH, aliases: pix, piex)
private_dot_{bashrc,zshrc} Bash and Zsh rc files
dot_vimrc, dot_vim/       Vim config, plugins, colors (vim-plug, ALE, molokai)
dot_tmux.conf             tmux
private_dot_npmrc.tmpl    npm config
private_dot_termux/       Termux properties (Android only)
modify_private_dot_gitconfig    Git config (merged, mode 0600)
dot_config/modify_mimeapps.list, modify_konsolerc  Merged into existing configs
dot_config/nvim/          Neovim minimal Lua config (zero plugins)
dot_config/{helix,zed}/   Helix and Zed editor settings
dot_config/wezterm/       WezTerm config
dot_config/yazi/          Yazi file manager
dot_config/mpv,aria2/     mpv and aria2 configs
dot_config/powershell/    PowerShell profile + Utils.psm1 module
dot_config/opencode/      opencode config (points at ~/.pi/agent/skills)
dot_config/Code/User/     VS Code settings + snippets
dot_config/systemd/user/  Linux systemd user services (dsh-web)
dot_pi/agent/             Pi config: APPEND_SYSTEM.md, settings modify template, themes
dot_pi/agent/exact_extensions/  Pi extensions (deployed as extensions/)
dot_pi/agent/exact_skills/      Pi skills (deployed as skills/)
dot_pi/agent/themes/            Pi themes, including flat.json
dot_local/scripts/        Scripts on PATH: exact_py → py/, sh/, ps1/
dot_local/scripts/exact_py/  stdlib-only Python (exact: strays removed on apply)
dot_local/share/konsole/  Konsole profile + One Dark and One Light schemes
AppData/Local/            Windows Terminal settings (Windows only)
private_dot_ssh/          SSH client config
.chezmoi.toml.tmpl        chezmoi config (autoAdd/autoCommit, no autoPush)
.chezmoiexternal.toml.tmpl  zsh plugin tarballs (non-Windows)
run_after_create-symlinks.sh.tmpl              Linux/Android: repair Code/User symlink each apply
run_onchange_after_systemd-user-reload.sh.tmpl Linux: reload user units
run_once_before_bootstrap-local-configs.ps1.tmpl    Windows: one-time bootstrap
run_onchange_after_create-junctions.ps1.tmpl        Windows: recreate junctions
```

`.chezmoiignore` keeps generated and runtime artifacts out of chezmoi's managed set: `~/.config/opencode/{cli.json,dcp.jsonc,package.json,service.json,…}` is written by opencode (service.json holds a password), and `node_modules`, `__pycache__`, `*.pyc`, and logs are generated. Never create, commit, or restore them.

## Project documents

`README.md` explains purpose, installation, and visible usage; `AGENTS.md` holds layout, conventions, constraints, and commands; `ARCHITECTURE.md` explains the major components and how they fit together; `TODO.md` tracks unfinished work. Update the file that owns a fact in the same piece of work. `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `TODO.md`, `LICENSE`, and `.github/` are in `.chezmoiignore`: never deployed.

Keep `AGENTS.md` current without waiting to be asked. Update it in the same piece of work when paths, commands, conventions, constraints, or policies change. If the project has no `AGENTS.md`, create one when a change establishes durable project-specific instructions that future agents need; keep it focused on layout, commands, conventions, and constraints.

## Commands

```bash
chezmoi diff                                  # verify before applying
chezmoi status                                # deploy drift, including forgotten files
chezmoi execute-template --file <template>    # render a template without deploying
chezmoi apply --force <target-path>           # targeted deploy; a full apply is the user's call
python3 script.py --help                      # verify a new CLI script parses
(cd dot_local/scripts/exact_py && python3 -m unittest discover -s exact_tests)
pi_lint_extensions.py --root "$PWD"           # from repo root; --dir <name> lints one extension
node --test                                   # per extension dir: runs every *.test.ts (Node >= 24)
```

Before reporting done, run the relevant checks for the area changed: Python tests for `exact_py`, `pi_lint_extensions.py` and `node --test` for changed extensions (`node --test` alone does not typecheck), and `chezmoi diff` after config edits.

Order matters: run `chezmoi diff`/`status` before `pi_lint_extensions.py` (its dangling `node_modules` symlinks can make chezmoi fail with `ENOENT`), and lint before `node --test` so extension imports resolve.

The one CI config is `.github/workflows/windows.yml`, the deliberate exception to "automation lives in chezmoi hooks": the Windows npm layout and `.cmd` launchers cannot be exercised on Linux. It runs the Python suite and `pi_lint_extensions`, installs pi twice and asserts the managed layout, installs nvim and checks the deployed profile's `PATH`, renders the dotfiles into a throwaway home (scripts and externals excluded), and PowerShell-parses the profile and the two Windows `run_` scripts. It triggers on PRs and on pushes touching `dot_local/scripts/exact_py/**`, `dot_pi/**`, `dot_config/powershell/**`, `run_*.ps1.tmpl`, or the workflow itself; trigger it manually with `gh workflow run windows`.

There are no linter/formatter configs and no Makefile; all other automation is chezmoi lifecycle hooks.

## Git and deployment

`chezmoi apply` and `sudo` are run by the user in their own terminal, never by the agent. Make and verify each self-contained piece of work, then commit it separately using explicit paths. Push only when explicitly requested. `.chezmoi.toml.tmpl` enables `autoAdd`/`autoCommit` with `autoPush = false` when git is on `PATH`, so the user's apply may also commit source edits. Never commit secrets; use OS credential stores.

Chezmoi source is the authoritative reference. Clone and grep it (`internal/chezmoi/` = mechanics and template funcs, `internal/cmd/` = commands):
`git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Filesystem policy

There is no in-process pi sandbox or permissions extension, so no `/permissions` modes or status-line indicator. The kernel boundary is the whole-process bubblewrap launchers `pi_sandbox` (`dot_local/scripts/exact_py/executable_pi_sandbox.py`) and `pier_sandbox` (`...executable_pier_sandbox.py`, shared logic in `_sandbox.py`), aliased to `pix` and `piex` in `dot_profile` so the bare `pi` and `pier` binaries stay unsandboxed. `PI_SANDBOX_MODE`/`PIER_SANDBOX_MODE` select `ww` (default), `ro` (launch directory read-only too), or `fa` (no sandbox).

- Root filesystem read-only in `ww`/`ro`. Writes are allowed to the launch directory (the workspace, overridable with `PI_SANDBOX_WORKSPACE`/`PIER_SANDBOX_WORKSPACE`), shared `~/.pi` agent state, caches, `~/.ssh/known_hosts`, and `/tmp`. Extra paths persist in `~/.config/pi_sandbox/rw` or `~/.config/pier_sandbox/rw` and can also be supplied with `PI_SANDBOX_RW` or `PIER_SANDBOX_RW`.
- `$XDG_RUNTIME_DIR` is replaced by a private tmpfs with only the container service socket and the ssh agent bound back. Every other host IPC endpoint is masked after the writable binds, including the system and session buses, the systemd user manager, pipewire, dconf, kwallet, at-spi, the yazi and mpv IPC endpoints, the X11/ICE/XIM sockets under `/tmp`, the tmux socket directory, and journald. Each would otherwise let the tool act on the host or run commands as the user outside the sandbox.
- The tool gets its own PID and SysV IPC namespaces, so it cannot signal the user's processes or touch their shared memory. The system SSH config drop-in directory is masked, and `known_hosts` stays writable so SSH and `git push` work under the user namespace.
- X11's abstract-namespace socket is the one endpoint that cannot be masked: bind mounts do not reach it, seccomp cannot inspect a sockaddr, and a network namespace would cut the network access the tool needs; the server refuses the handshake without a cookie.
- Rootless podman cannot build its own user namespace under bwrap (`no_new_privs` defeats `newuidmap`), so both launchers point `CONTAINER_HOST` at the user's `podman.socket` when it exists. Containers then run with the user's own permissions, outside the writable allowlist.
- The agent's own `bash` calls run with the account's OS permissions, so they are constrained only when the parent application was started through one of these launchers.

Keep this section to invariants; `_sandbox.py` and `dot_local/scripts/exact_py/AGENTS.md` own the implementation detail.
