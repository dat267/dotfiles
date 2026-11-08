# AGENTS.md

Guidelines for AI agents working in this dotfiles repository.

## Chezmoi filename conventions

| Prefix | Effect |
|---|---|
| `dot_` | Deploys as a dotfile (`dot_vimrc` → `~/.vimrc`) |
| `private_` | Mode 0600, or 0700 on a directory. Never remove it from SSH or gitconfig files |
| `executable_` | Sets the executable bit; the prefix is stripped |
| `modify_` | Merges into the existing target at deploy time instead of replacing it |
| `exact_` | The directory's contents are exact: unmanaged files are removed on apply |
| `run_once_`, `run_onchange_` | Lifecycle hooks |
| `*.tmpl` | Go template |

Prefixes stack, as in `private_executable_` or `executable_dot_`.

Edit the chezmoi source, never the deployed target. Keep `{{- ... -}}` whitespace trimming and `{{ if eq .chezmoi.os "..." }}` guards intact. In Yazi's unix rules, never quote `%s` or `%s1`, because Yazi already escapes those paths. The Windows rules quote them on purpose; see `dot_config/yazi/yazi.toml`.

## Layout

Notable source → deployed mappings:

| Source | Deployed |
|---|---|
| `dot_local/scripts/exact_py/` | `~/.local/scripts/py/` (on `PATH`) |
| `dot_pi/private_agent/exact_extensions/` | `~/.pi/agent/extensions/` |
| `dot_pi/private_agent/exact_skills/` | `~/.pi/agent/skills/` |
| `dot_pi/private_agent/private_APPEND_SYSTEM.md` | `~/.pi/agent/APPEND_SYSTEM.md` (mode 0600) |
| `dot_pi/private_agent/modify_settings.json` | `~/.pi/agent/settings.json` (merged) |
| `dot_pi/private_agent/modify_private_models.json` | `~/.pi/agent/models.json` (merged, mode 0600). Caps every 1M-context model at 500k by exact ID; add new 1M models to its list |
| `dot_config/opencode/private_opencode.json` | `~/.config/opencode/opencode.json` |

```
dot_profile               Shell env for bash/zsh (PATH, aliases: pix, piex)
dot_zshenv, dot_zprofile  zsh startup files; both defer PATH to dot_profile
private_dot_{bashrc,zshrc} Bash and Zsh rc files
dot_vimrc, dot_vim/       Vim config, plugins, colors (vim-plug, ALE, molokai)
dot_tmux.conf             tmux
private_dot_npmrc.tmpl    npm config
dot_config/private_pip/   pip config (`user = true`; deployed on Linux/Android only)
private_dot_termux/       Termux properties (Android only)
modify_private_dot_gitconfig    Git config (merged, mode 0600)
dot_config/modify_mimeapps.list, modify_konsolerc  Merged into existing configs
dot_config/nvim/          Neovim minimal Lua config (zero plugins)
dot_config/{helix,zed}/   Helix and Zed editor settings
dot_config/wezterm/       WezTerm config
dot_config/yazi/          Yazi file manager
dot_config/lf/            lf file manager (wrap-around navigation)
dot_config/{mpv,aria2}/   mpv and aria2 configs
dot_config/powershell/    PowerShell profile + Utils.psm1 module
dot_config/opencode/      opencode config (points at ~/.pi/agent/skills)
dot_config/Code/User/     VS Code settings + snippets
dot_config/systemd/user/  Linux systemd user services (dsh-web)
dot_pi/private_agent/     Pi config (deployed as ~/.pi/agent, mode 0700 to match what pi creates)
dot_pi/private_agent/exact_extensions/  Pi extensions (deployed as extensions/)
dot_pi/private_agent/exact_skills/      Pi skills (deployed as skills/); exact_brainstorming/ holds its Superpowers attribution and license
dot_pi/private_agent/themes/            Pi themes, including flat.json
dot_local/scripts/        Scripts: exact_py → py/, sh/, ps1/ (on PATH); js/ (Node, playwright-core; not on PATH)
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

`.chezmoiignore` keeps generated and runtime files out of chezmoi's managed set. opencode writes `~/.config/opencode/{cli.json,dcp.jsonc,package.json,service.json,…}` itself, and `service.json` holds a password. `node_modules`, `__pycache__`, `*.pyc`, and logs are build output. Never create, commit, or restore any of them.

## Project documents

Each fact has one home:

- `README.md`: purpose, installation, and visible usage.
- `AGENTS.md`: layout, conventions, constraints, and commands.
- `ARCHITECTURE.md`: the major components and how they fit together.
- `TODO.md`: unfinished work.

Write markdown with each paragraph and list item on one line. Tables, code blocks, and the layout tree keep their own lines.

When a change alters a fact, update the file that owns it in the same piece of work. These four files, `LICENSE`, and `.github/` are in `.chezmoiignore` and never deploy.

Keep `AGENTS.md` current without being asked: update it whenever paths, commands, conventions, constraints, or policies change, and keep it to those.

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

Before reporting done, run the checks for the area you changed:

- `exact_py`: the Python tests.
- Extensions: `pi_lint_extensions.py`, then `node --test`. `node --test` alone does not typecheck.
- Config: `chezmoi diff`.

Order matters. Run `chezmoi diff` or `status` before `pi_lint_extensions.py`, because the linter's `node_modules` symlinks can dangle and make chezmoi fail with `ENOENT`. Lint before `node --test` so extension imports resolve.

### CI

The only CI config is `.github/workflows/windows.yml`. It is the deliberate exception to "automation lives in chezmoi hooks", because the Windows npm layout and `.cmd` launchers cannot be exercised on Linux. It:

- runs the Python suite and `pi_lint_extensions`;
- installs pi twice and asserts the managed layout;
- installs nvim and checks the deployed profile's `PATH`;
- renders the dotfiles into a throwaway home, excluding scripts and externals;
- PowerShell-parses the profile, `Utils.psm1`, and the two Windows `run_` scripts, and parses the hooks again under Windows PowerShell 5.1.

The 5.1 pass exists because chezmoi falls back to 5.1 when pwsh is missing. It is also why the hooks must stay ASCII: chezmoi writes them without a BOM, and 5.1 decodes BOM-less files with the ANSI code page.

The workflow runs on PRs and on pushes that touch `dot_local/scripts/exact_py/**`, `dot_pi/**`, `dot_config/powershell/**`, `run_*.ps1.tmpl`, or the workflow itself. Run it by hand with `gh workflow run windows`.

There are no linter or formatter configs and no Makefile. All other automation is chezmoi lifecycle hooks.

## Git and deployment

The user runs `chezmoi apply` and `sudo` in their own terminal; the agent never does. Make and verify each self-contained piece of work, then commit it on its own with explicit paths. Push only when explicitly asked.

When git is on `PATH`, `.chezmoi.toml.tmpl` turns on `autoAdd` and `autoCommit` with `autoPush = false`, so the user's apply may also commit source edits. Never commit secrets; they belong in OS credential stores.

chezmoi's own source is the authoritative reference. Clone it and grep `internal/chezmoi/` for mechanics and template functions, or `internal/cmd/` for commands: `git clone --depth 1 https://github.com/twpayne/chezmoi.git /tmp/chezmoi`

## Filesystem policy

Pi has no in-process sandbox or permissions extension here, so there are no `/permissions` modes and no status-line indicator. The boundary is in the kernel: the bubblewrap launchers `pi_sandbox` (`dot_local/scripts/exact_py/executable_pi_sandbox.py`) and `pier_sandbox` (`…/executable_pier_sandbox.py`) wrap the whole process, with shared logic in `_sandbox.py`. `dot_profile` aliases them to `pix` and `piex`, so the bare `pi` and `pier` binaries stay unsandboxed. `PI_SANDBOX_MODE` or `PIER_SANDBOX_MODE` selects `ww` (the default), `ro` (the launch directory is read-only too), or `fa` (no sandbox).

- In `ww` and `ro` the root filesystem is read-only. Writes are allowed to the launch directory (the workspace, overridable with `PI_SANDBOX_WORKSPACE` or `PIER_SANDBOX_WORKSPACE`), the shared `~/.pi` agent state, caches, `~/.ssh/known_hosts`, and `/tmp`. Extra writable paths can be listed in `~/.config/pi_sandbox/rw` or `~/.config/pier_sandbox/rw`, or passed in `PI_SANDBOX_RW` or `PIER_SANDBOX_RW`.
- `$XDG_RUNTIME_DIR` is replaced by a private tmpfs, with only the container service socket and the ssh agent bound back in. Every other host IPC endpoint is masked after the writable binds: the system and session buses, the systemd user manager, pipewire, dconf, kwallet, at-spi, the yazi and mpv IPC endpoints, the X11/ICE/XIM sockets under `/tmp`, the tmux socket directory, and journald. Any of them would let the tool act on the host, or run commands as the user outside the sandbox.
- The tool gets its own PID and SysV IPC namespaces, so it cannot signal the user's processes or touch their shared memory. The system SSH config drop-in directory is masked, and `known_hosts` stays writable so SSH and `git push` work inside the user namespace.
- X11's abstract-namespace socket is the one endpoint that cannot be masked. Bind mounts do not reach it, seccomp cannot inspect a sockaddr, and a network namespace would cut off the network the tool needs. The X server still refuses the handshake without a cookie.
- Rootless podman cannot build its own user namespace under bwrap, because `no_new_privs` defeats `newuidmap`. Both launchers therefore point `CONTAINER_HOST` at the user's `podman.socket` when it exists, and containers run with the user's own permissions, outside the writable allowlist.
- The agent's own `bash` calls run with the account's full OS permissions. They are constrained only when the parent application was started through one of these launchers.

Keep this section to invariants. `_sandbox.py` and `dot_local/scripts/exact_py/AGENTS.md` own the implementation detail.
