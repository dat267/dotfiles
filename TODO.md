# TODO

## Bugs

All confirmed findings are repaired; the tests that pin them live in `tests/`.

- [ ] MAIN-17 low: `serve`'s handler has no per-connection timeout, so a client that announces a body and then sends nothing (or a refused request whose response the client never reads) ties up a request thread until the socket dies.
- [ ] MAIN-18 low: several installers build their destination with `expanduser("~/.local/bin")` or `expanduser("~/Apps")` on Windows too, so under an MSYS2/Cygwin Python they land in the emulated home that the Windows PATH does not contain. `_shared.windows_home` exists for this; the sites are the module-level `INSTALL_DIR` constants and `install_gcloud.py`'s Windows branch.
