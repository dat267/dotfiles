# Design: Remove custom snippets, keep pure gopls autocomplete

Date: 2026-08-09
Status: Approved

## Goal

Remove the custom Go snippet system from the Neovim config so completion comes
purely from gopls, while keeping the on-type autocomplete UX and leaving the
architecture open to re-adding snippets later.

## Background

`lua/snippets.lua` defines custom snippets (`iferr`, `main`, `struct`, `iface`),
injects them into the LSP completion list by monkeypatching `vim.fn.complete`,
and expands them on `CompleteDone` via `vim.snippet.expand`. gopls does not
provide these snippets natively (they ship with the vscode-go extension), so
they were custom. The user now wants them removed for a cleaner codebase.

## Changes

1. **Delete `dot_config/nvim/lua/snippets.lua`** — the whole module.
2. **`dot_config/nvim/init.lua`** — remove the `require("snippets").setup()`
   line.
3. **`dot_config/nvim/lua/lsp.lua`** — replace
   `provider.triggerCharacters = require("snippets").merge_trigger_chars(...)`
   with an inline local `merge_trigger_chars` function (same identifier-char
   extension logic: server chars + `a-zA-Z0-9_`), so `vim.lsp.completion.enable`
   autotrigger still fires on typing. The insert-mode `<BS>`/`<Del>`/`<Left>`/
   `<Right>` re-trigger keymaps call `vim.lsp.completion.get()` directly and are
   unchanged.

## Kept (out of scope)

- On-type autotrigger (`vim.lsp.completion.enable`, `autotrigger = true`).
- Trigger-character extension (inlined into `lsp.lua`).
- Backspace/delete/arrow re-trigger keymaps.
- `whichwrap`, inlay-hint insert toggle, gopls `experimentalPostfixCompletions`.

## Future snippets

No stub code is left behind. Re-adding snippets later means recreating a small
module that (a) merges trigger chars and (b) optionally patches `vim.fn.complete`
— the interception point and `vim.snippet` engine remain available.

## Verification

Headless (nvim 0.12.4):
1. Config smoke: `nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa`.
2. `grep -r snippets dot_config/nvim/` returns nothing.
3. `vim.fn.complete` is unpatched (no `CompleteDone` autocmd, no `[snip]` menu items).
4. gopls still attaches on-type with merged trigger chars (existing `test_lsp`).

## Files touched

- Delete `dot_config/nvim/lua/snippets.lua`
- `dot_config/nvim/init.lua`
- `dot_config/nvim/lua/lsp.lua`
