# dot_local/exact_scripts/exact_py/: Python utility scripts

Standard-library Python tools that chezmoi deploys to `~/.local/scripts/py/`, which `dot_profile` puts on `PATH`. Every script carries the `executable_` prefix; the shared modules (`_*.py`) do not.

## Naming

- The deployed name is the filename minus `executable_`. Words are separated by underscores: `install_aws.py`, `yazi_ffmpeg_split.py`, `url_decode_rename.py`.
- Related scripts share a prefix: `install_<tool>.py` installers and `yazi_*.py` Yazi helpers.
- Standalone tools use a bare name: `cloudsh.py`, `dotfiles.py`, `lsp.py`, `sysinfo.py`, and `mpv`, an extensionless drop-in.

## Scripts

### Installers

- `executable_install_*.py`: tool installers. Most download the latest GitHub release into `~/.local/bin/`. `install_pi.py` instead runs the platform's official installer (`https://pi.dev/install.sh` under sh on POSIX, `install.ps1` under PowerShell on Windows), detached from the terminal so its tty-gated prompts take their non-interactive defaults.
- `executable_install_tools.py`, `executable_uninstall_tools.py`: install or remove the tool binaries published in this repo's own GitHub releases (`dat267/dotfiles`).
- `executable_lsp.py`: installs LSP servers (gopls, pyright, and others).
- `executable_gim.py`: installs private Go binaries over SSH (`gim <repo[@version]>`).

### Pi tooling

- `executable_pi_sandbox.py`, `executable_pier_sandbox.py`: the bubblewrap launchers for pi and pier (aliases `pix` and `piex`). Each is a thin `Profile` declaration over `_sandbox.py`.
- `executable_pi_lint_extensions.py`: runs `tsc --strict` over each pi extension directory, creating the per-directory `node_modules` symlinks on demand. It installs the pinned TypeScript into `~/.cache/pi_lint_extensions/` and runs `node …/tsc` directly, so no shebang is ever executed.
- `executable_hyper_catalog.py`: regenerates the hyper provider's model catalog (a pi extension) from the live `/v1/models` API. `--check` reports drift without writing.

### Yazi helpers

- `executable_yazi_*.py`: media and translation helpers bound in Yazi's `keymap.toml`.

### Everyday tools

- `executable_cloudsh.py`: SSH into GCP Cloud Shell. It hands the tunnel and ssh to `gcloud cloud-shell ssh` (whose `--dry-run` stops the tunnel before exiting) and passes keepalives through `--ssh-flag`. It retries interactive sessions that drop with exit 255, but not one-shot commands, which could otherwise run twice. It filters gcloud's tunnel status lines and teardown tracebacks out of stderr.
- `executable_dotfiles.py`: rclone and git sync (`dotfiles up`, `dotfiles down`).
- `executable_ntfy.py`: push notifications through ntfy.sh or a self-hosted server. The body comes from an argument or stdin; the target from `--topic`, `$NTFY_TARGET`, or `~/.config/ntfy/target`.
- `executable_serve.py`: LAN file sharing. Serves a directory or one file and prints URLs and an ASCII QR code, with optional `--token`, `--upload`, and `--once`, and moves to the next port when one is taken. The single-file guard compares decoded paths, so a name with a space or non-ASCII character works. Uploads are capped at 100 MB, refused with 413 before the body is read. The QR code needs `qrencode`; without it only the URLs print.
- `executable_extract.py`: archive extraction. zip and tar use the standard library, and tar symlinks and hardlinks are recreated as links; .7z, .lzma, .lz4 and .rar use `7z` and `unrar`, and a file that is not an archive is refused rather than handed to them. It refuses absolute or `..` member paths (link targets included), and a non-empty destination unless `-f`/`--force` is given. `-C` sets the destination, `-l` lists members without extracting, and `-q` reports only errors.
- `executable_crypt.py`: authenticated file encryption with ChaCha20-Poly1305 and scrypt, in pure Python.
- `executable_dua.py`: a disk usage analyzer in the style of dua. It shows totals or the largest files, scans with one forked worker per core (`-t` sets the count), and counts hardlinks once unless given `-l`.
- `executable_mdk.py`: one-shot markdown search. ripgrep lists matching lines, fzf picks one, and `$EDITOR` opens at the match (alias `mdk`).
- `executable_ports.py`: listening sockets from `ss -tlnp`, classified as exposed, bound, or local. Scope-qualified IPv6 listeners (`[addr]%iface:port`) parse like any other.
- Converters for shell pipelines: `executable_jsonfmt.py` (pretty-print, minify, or sort JSON), `executable_epoch.py` (epoch to and from ISO), `executable_csvtable.py` (CSV to an aligned table), `executable_dupfind.py` (duplicate files by size and hash), `executable_b64.py` (base64 for binary data).
- `executable_sysinfo.py`, `executable_url_decode_rename.py`, `executable_mpv`.

### Shared modules

- `_shared.py`: platform detection, colored logging, and download helpers, including `install_github_binary` for the single-binary release installers.
- `_pi_install.py`: resolves the pi package and launcher, for both managed releases and legacy npm installs.
- `_sandbox.py`: the bubblewrap launcher behind `pi_sandbox.py` and `pier_sandbox.py`. Each of those declares a `Profile` (tool, env prefix, unsandboxed subcommands, agent-state variables, host service sockets) and delegates here, so the writable allowlist, argv assembly, probe, and fallbacks exist once. It replaces `$XDG_RUNTIME_DIR` with a private tmpfs, binds back only the profile's socket and the ssh agent, and, after the writable binds, masks the host IPC endpoints outside it (system bus, X11/ICE/XIM, tmux, journald), since each is a way to act on the host. It also unshares the PID and SysV IPC namespaces. X11's abstract socket is the one endpoint it cannot mask.

## Conventions

- Shebang: `#!/usr/bin/env python3`.
- Standard library only.
- Data goes to stdout. Pipeline tools print messages to stderr with `eprint()`; installers report progress with `_shared.log()`.
- Yazi scripts end with `input("Press Enter to continue...")` so their output stays visible.
- Yazi wraps paths in single quotes; strip them with `if len(p) >= 2 and p[0] == p[-1] and p[0] in "'\"": p = p[1:-1]`.
- Installers download the latest release, extract it, place the binary, and verify it with `--version`.

## Tests

- `exact_tests/` (deployed as `tests/`) holds stdlib `unittest` modules, one per script. Run `python3 -m unittest discover -s exact_tests`.
- `exact_tests/_loader.py` imports scripts by path, handling the `executable_` prefix, hyphenated or underscored stems, and the extensionless `mpv`.
- Network and install side effects are mocked. Tests cover pure logic and the commands `main()` builds.

## Don't

- Add pip dependencies.
- Remove the `executable_` prefix; chezmoi strips it on deploy.
- Hardcode versions; installers detect the latest release.
