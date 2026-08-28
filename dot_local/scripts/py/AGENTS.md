# dot_local/scripts/py/ — Python Utility Scripts

33 Python scripts chezmoi-deployed to `~/.local/bin/` (on PATH). All use `executable_` prefix.

## Structure

- `executable_yazi-*.py` — 10 Yazi media/translate helpers, invoked via `keymap.toml` bindings
- `executable_install_*.py` — 17 tool installers, each downloads latest GitHub release to `~/.local/bin/`
- `executable_dotfiles.py` — rclone + git sync (`dotfiles up`/`dotfiles down`)
- `executable_codi.py` — Docker isolate container (builds `opencode-isolate:latest`)
- `executable_lsp.py` — LSP server installer (gopls, pyright, etc.)
- `executable_start-awsvpn.py` — OpenVPN + SAML auth
- `executable_cloudsh.py` — GCP Cloud Shell SSH tunnel
- `executable_sysinfo.py`, `executable_url_decode_rename.py`, `executable_mpv`
- `_shared.py` — shared module (platform detection, colored logging, helpers)

## Conventions

- Shebang: `#!/usr/bin/env python3`
- `eprint()` for user-facing messages (stderr); `print()` for pipeline output (stdout)
- Standard library only; no pip dependencies
- Yazi scripts end with `input("Press Enter to continue...")` for terminal visibility
- Strip Yazi's single-quote-wrapped paths: `if len(p) >= 2 and p[0] == p[-1] and p[0] in "'\"": p = p[1:-1]`
- Tool installers: download latest release, extract, place binary, verify with `--version`

## Anti-Patterns

- Do NOT add pip dependencies — standard library only
- Do NOT remove `executable_` prefix — chezmoi strips it on deploy
- Do NOT hardcode versions — installers auto-detect latest release