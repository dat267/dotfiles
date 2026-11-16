# TODO

## Bugs

All confirmed findings are repaired; the tests that pin them live in `tests/`.

- [ ] MAIN-17 low: `serve`'s handler has no per-connection timeout, so a client that announces a body and then sends nothing (or a refused request whose response the client never reads) ties up a request thread until the socket dies.
- [ ] MAIN-18 low: several installers build their destination with `expanduser("~/.local/bin")` or `expanduser("~/Apps")` on Windows too, so under an MSYS2/Cygwin Python they land in the emulated home that the Windows PATH does not contain. `_shared.windows_home` exists for this; the sites are the module-level `INSTALL_DIR` constants and `install_gcloud.py`'s Windows branch.
- [ ] MAIN-19 low: `crypt` derives its key with scrypt and silently falls back to PBKDF2 when `hashlib.scrypt` is missing, and the file header records no KDF, so a file written on a scrypt-less Python cannot be decrypted elsewhere ("Bad passphrase or corrupted data"). A fix changes the file format (a KDF id in a v2 header), so it needs a decision before implementation; the pinning test would monkeypatch `hashlib.scrypt` to raise and then decrypt with scrypt available.
- [ ] MAIN-20 low: `private_dot_ssh/private_config` sets `StrictHostKeyChecking no` and `UserKnownHostsFile=/dev/null` for `Host *`, so no host key is ever verified or recorded, while `pi_sandbox`'s docstring and `AGENTS.md` justify the writable `~/.ssh/known_hosts` with "so new host keys can be recorded". Either the relaxations belong on the specific aliases (`nexus`, `citadel`, `outpost`) and the wildcard should keep checking, or the two documents should stop claiming known_hosts matters. Both are trust policy, so this needs a decision.
