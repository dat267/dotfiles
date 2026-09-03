# dot_local/scripts/py/ — Python Utility Scripts

Python utility scripts chezmoi-deployed to `~/.local/bin/` (on PATH). All use `executable_` prefix.

## Structure

- `executable_yazi-*.py` — Yazi media/translate helpers, invoked via `keymap.toml` bindings
- `executable_install_*.py` — Tool installers, each downloads latest GitHub release to `~/.local/bin/`
- `executable_dotfiles.py` — rclone + git sync (`dotfiles up`/`dotfiles down`)
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

## Tests

- `tests/` — stdlib `unittest`, one module per script, run with `python3 -m unittest discover -s tests`
- `tests/_loader.py` imports scripts by path (handles `executable_` prefix, hyphens/underscores, extensionless `mpv`)
- Network and install side effects are mocked; only pure logic and main()-driven command construction are tested
- `@unittest.expectedFailure` marks verified script bugs (see class docstrings in `test_cloudsh.py`, `test_install_android_nerdfont.py`)

## Anti-Patterns

- Do NOT add pip dependencies — standard library only
- Do NOT remove `executable_` prefix — chezmoi strips it on deploy
- Do NOT hardcode versions — installers auto-detect latest release