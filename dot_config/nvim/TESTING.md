# Neovim Testing Reference

The nvim config in `dot_config/nvim/` is **zero-plugin** (built-ins only: `vim.lsp`, native treesitter, netrw, custom statusline/brackets/comments/format). Modules load from `init.lua` in order: options, keymaps, autocmds, treesitter, netrw, statusline, brackets, comments, format, lsp.

## Headless testing

Logic and integration can be verified, but NOT visuals/UI:

```sh
# Config loads cleanly
nvim --headless -u ~/.config/nvim/init.lua +'lua print("ok")' +qa

# Test per-filetype LSP attach + clients
nvim --headless -u ~/.config/nvim/init.lua +'edit file.go' \
  +'lua vim.wait(800); for _,c in ipairs(vim.lsp.get_clients({bufnr=0})) do print(c.name) end' +qa
```

## Key gotchas

- **`nvim_input()` hangs headless** — don't use it to simulate typing. `normal! iX` inserts fine; feedkeys in insert mode often fails to dispatch callback keymaps.
- **Insert-mode keymaps/autocmds** (like `InsertCharPre` brackets, `<C-Space>` omni) can't be fully verified headless — test the decision logic directly by invoking module functions or replicating the check.
- **`nvim_feedkeys` needs `nvim_replace_termcodes("<Left>", true, false, true)`** — a literal `"<Left>"` string inserts as text, not a keypress (e.g. produced `()<Left>`).
- **Test files must be inside the workspace** (`/tmp/opencode/**` or repo) — external dirs are allowed only after confirmation, but keeping tests local avoids side effects.
- **`vim.lsp.enable` requires `filetypes` per server**; without it servers attach to every buffer. Only enable servers whose binary exists (`vim.fn.executable`), else loading a file errors/spams.
- **LSP formatting needs an attached client**: `vim.lsp.buf.format`; external formatter fallback in `lua/format.lua` uses `vim.fn.executable` to pick gofmt/rustfmt/black/prettier/shfmt/etc. and silently skips when missing.
- When testing the source config (not deployed), prepend rtp: `nvim --headless --cmd 'set rtp^=/home/dat/.local/share/chezmoi/dot_config/nvim' -u dot_config/nvim/init.lua`.

## Per-module verification checklist

Headless, each line is one check:

| Module | What to verify | Headless one-liner |
| ------ | -------------- | ------------------ |
| options | settings applied | `+'lua print(vim.o.completeopt, vim.bo.tabstop)'` |
| keymaps | mappings registered | `+'lua for _,m in ipairs(vim.api.nvim_buf_get_keymap(0,"n")) do if m.lhs=="<leader>w" then print(m.lhs) end end'` |
| autocmds | hooks exist | `+'lua print(#vim.api.nvim_get_autocmds({event="BufWritePre"}))'` |
| treesitter | parser available | `+'edit f.go' +'lua vim.treesitter.start(); print("ts ok")'` |
| netrw | options set | `+'lua print(vim.g.netrw_liststyle, vim.g.netrw_banner)'` |
| statusline | builds valid string | `+'lua print(type(require("statusline").build()) == "string")'` |
| brackets | decision logic | `+'lua ... (replicate pair/skip/backspace checks, feedkeys won't dispatch)'` |
| format | formatter chosen | `+'lua local m=require("format")'` + filetype-specific `:w` on a sample file |
| lsp | client attaches + completes | `+'edit f.go' +'lua vim.wait(800); vim.lsp.buf_request(0,"textDocument/completion",{textDocument={uri=vim.uri_from_bufnr(0)},position={0,0}},function(_,r) print(#(r and r.items or {})) end); vim.wait(1000)'` |
| lsp | diagnostics flow | `+'edit f.go' +'lua vim.wait(800); print(#vim.diagnostic.get(0))'` |

General rules: LSP checks need `vim.wait()` after load (clients attach async); invoke module functions directly rather than simulating keypresses; keep test files under `/tmp/opencode/**`.
