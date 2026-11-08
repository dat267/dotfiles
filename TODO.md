# TODO

## Bugs

- [ ] MAIN-1 high: `install_code` and `install_rclone` always fail with `NameError: install_release_binary is not defined` (never imported), so neither CLI installs anything.
- [ ] MAIN-2 high: `lsp.py`'s Lua recipe calls `create_proxy(lua_bin, "lua-language-server")` with the platform argument missing, so a fresh install and a re-link both raise `TypeError` after the download.
- [ ] MAIN-3 medium: `serve --only <name>` 404s whenever the shared file's name has a space or non-ASCII character, because the guard compares the percent-encoded request path to the raw name.
- [ ] MAIN-4 medium: `extract` materializes tar symlinks as copies of their target, so extracted trees lose their links and duplicate the bytes.
- [ ] MAIN-5 low: `extract` skips tar hardlink members without reporting them, and `serve`'s docstring raises a `SyntaxWarning` for `D:\` under Python 3.12+.

## Later

- [ ] When a Windows-only path outside the workflow's triggers changes, run the Windows workflow by hand (`gh workflow run windows`). Pushes start it only when they touch `exact_py`, `dot_pi`, `dot_config/powershell`, or the `run_*.ps1.tmpl` files, so a change to `AppData/` alone does not.
