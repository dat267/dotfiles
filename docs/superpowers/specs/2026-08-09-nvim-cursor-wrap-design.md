# Design: Line-boundary cursor wrap for Neovim

Date: 2026-08-09
Status: Approved

## Goal

Make the cursor wrap across line boundaries when moving horizontally past the
start/end of a line.

## Change

`dot_config/nvim/lua/options.lua`: append `h,l,<,>,[,]` to `whichwrap`:

```lua
opt.whichwrap:append("h,l,<,>,[,]")
```

Effective value `b,s,h,l,<,>,[,]`:
- `h`/`l` and `<Left>`/`<Right>` wrap in normal mode.
- `<Left>`/`<Right>` wrap in insert mode (`[`/`]`).
- `b`/`s` (backspace/space wrap in insert mode) were already the default.

## Interaction with existing config

The insert-mode `<Left>`/`<Right>` retrigger keymaps (lsp.lua) feed the native
key with no-remap, so wrapping is preserved; the deferred completion re-trigger
may fire if the wrapped-to position sits on an identifier, consistent with the
existing "show on cursor move" behavior.

## Verification

Headless (nvim 0.12.4): config smoke test; assert `vim.o.whichwrap` equals
`b,s,h,l,<,>,[,]` after loading options; assert `h`/`l`/arrow behavior at a
line boundary via `nvim_win_set_cursor` + `normal!` movement.

## Files touched

- `dot_config/nvim/lua/options.lua`
