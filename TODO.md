# TODO

## Bugs

All confirmed findings are repaired; the tests that pin them live in `tests/`.

- [ ] MAIN-17 low: `serve`'s handler has no per-connection timeout, so a client that announces a body and then sends nothing (or a refused request whose response the client never reads) ties up a request thread until the socket dies.
