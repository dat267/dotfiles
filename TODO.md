# TODO

## Now

- [ ] Confirm the `mimeapps.list` TTY conflict on a real full `chezmoi apply`, then either fix the managed entry or keep documenting the targeted-apply workaround. `chezmoi status` is currently clean.

## Next

- [ ] Decide how to cap Pi's context window for large-catalog models: enumerated `modelOverrides` per enabled model pattern, or an extension that registers providers with a lower `contextWindow`.
- [ ] Extend `install_nerd_font.py` to take a font name, so Iosevka or Iosevka Term can be installed alongside Hack.
- [ ] Replace the dropped bottom config with a non-interactive status script, if the shell still needs at-a-glance system state.

## Later

- [ ] Run `documentation` periodically so the five project files do not drift.
- [ ] Re-check the Windows workflow when a Windows-only path changes outside `exact_py`, `dot_pi`, `dot_config/powershell`, and the `run_*.ps1.tmpl` files it triggers on.
