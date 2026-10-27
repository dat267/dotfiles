# TODO

## Now

- [ ] Remove or repoint `dot_pi/agent/exact_extensions/exact_auto-default/node_modules/@earendil-works/chord`. It targets `~/.pi/agent/install/releases/1.1.0/...`, which no longer exists, and it makes `chezmoi execute-template` fail when the source is the repo. The six `test_lifecycle_hooks` errors are downstream of it.
- [ ] Confirm the `mimeapps.list` TTY conflict on a real full `chezmoi apply`, then either fix the managed entry or keep documenting the targeted-apply workaround. `chezmoi apply --dry-run` is currently clean.

## Next

- [ ] Decide how to cap Pi's context window for large-catalog models: enumerated `modelOverrides` per enabled model pattern, or an extension that registers providers with a lower `contextWindow`.
- [ ] Extend `install_nerd_font.py` to take a font name, so Iosevka or Iosevka Term can be installed alongside Hack.
- [ ] Replace the dropped bottom config with a non-interactive status script, if the shell still needs at-a-glance system state.

## Later

- [ ] Run `doc-maintenance` periodically so the five project files do not drift.
- [ ] Re-check the Windows workflow when a Windows-only path changes outside `exact_py`, `dot_pi`, `dot_config/powershell`, and the `run_*.ps1.tmpl` files it triggers on.
