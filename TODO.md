# TODO

## Bugs

All confirmed findings are repaired; the tests that pin them live with their modules.

- [ ] MAIN-17 low: `serve`'s handler has no per-connection timeout, so a client that announces a body and then sends nothing (or a refused request whose response the client never reads) ties up a request thread until the socket dies.

## Later

- [ ] When a Windows-only path outside the workflow's triggers changes, run the Windows workflow by hand (`gh workflow run windows`). Pushes start it only when they touch `exact_py`, `dot_pi`, `dot_config/powershell`, or the `run_*.ps1.tmpl` files, so a change to `AppData/` alone does not.
