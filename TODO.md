# TODO

## Bugs

All confirmed findings are repaired; the tests that pin them live with their modules.

- [ ] MAIN-6 open decision: `serve --upload` reads whatever `Content-Length` the client sends, with no cap, so one request can make the server buffer unbounded input in memory. Needs a size limit and an answer for oversized bodies.

## Later

- [ ] When a Windows-only path outside the workflow's triggers changes, run the Windows workflow by hand (`gh workflow run windows`). Pushes start it only when they touch `exact_py`, `dot_pi`, `dot_config/powershell`, or the `run_*.ps1.tmpl` files, so a change to `AppData/` alone does not.
