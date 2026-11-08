# TODO

## Later

- [ ] When a Windows-only path outside the workflow's triggers changes, run the Windows workflow by hand (`gh workflow run windows`). Pushes start it only when they touch `exact_py`, `dot_pi`, `dot_config/powershell`, or the `run_*.ps1.tmpl` files, so a change to `AppData/` alone does not.
