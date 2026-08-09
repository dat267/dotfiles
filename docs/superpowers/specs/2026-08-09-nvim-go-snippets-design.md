# Design: Zero-plugin Go snippets + on-type LSP completion for Neovim

Date: 2026-08-09
Status: Approved

## Goal

Add quick Go snippets to the Neovim config (`dot_config/nvim/`) that appear in the
existing LSP completion menu, and switch completion from manual `<C-Space>` to
automatic on-type completion. The config is deliberately **zero-plugin**, so this
uses only Neovim 0.11+ built-ins (`vim.lsp`, `vim.snippet`). Must work
cross-platform (Linux, Windows, Android/Termux) and stay performant.

## Background facts (verified against Neovim v0.12.4)

- `vim.snippet` provides a native snippet engine: `expand()`, `jump()`,
  `active()`, `stop()`. Tabstop navigation uses LSP snippet syntax
  (`${1:placeholder}`, `$0`). `<Tab>` is **not** mapped by default; the
  docs show a keymap to add.
- LSP completion (`vim.lsp.completion`) is asynchronous: the omnifunc returns
  `-2`, and results are delivered later via `vim.fn.complete(start_col, matches)`
  (runtime/lua/vim/lsp/completion.lua:1059). The response handler discards
  results unless Neovim is in insert mode.
- `vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })`
  triggers completion on the server's `completionProvider.triggerCharacters`.
  To trigger on every keypress, extend `triggerCharacters` before enabling
  (`:h lsp-autocompletion`). The module debounces (25 ms + adaptive RTT).
- gopls declares `completionProvider.triggerCharacters = ["."]` only.
- Monkeypatching `vim.fn.complete` works (verified headless): injected items
  appear in the LSP completion list.

## Design

### 1. On-type completion (`dot_config/nvim/lua/lsp.lua`)

In the existing `LspAttach` autocmd, when the client supports
`textDocument/completion`:

1. Merge identifier characters (`a-z A-Z 0-9 _`) into the client's
   `server_capabilities.completionProvider.triggerCharacters` (deduped with the
   server's own triggers). This is done per-client on attach.
2. Call `vim.lsp.completion.enable(true, client.id, args.buf, { autotrigger = true })`.
3. Remove the insert-mode `<C-Space>` mapping (currently
   `vim.keymap.set("i", "<C-Space>", "<C-x><C-o>", ...)`).
   Keep `vim.bo[bufnr].omnifunc = "v:lua.vim.lsp.omnifunc"` so `<C-x><C-o>`
   remains a manual fallback.

Rationale: every-keystroke autocompletion with a curated trigger set (identifier
chars only, not all 32–126 printable chars) avoids spamming requests on spaces and
punctuation. Latency is handled by the native debounce; no custom timers.

### 2. Snippet module (`dot_config/nvim/lua/snippets.lua`, new)

- `snippets` table keyed by filetype; initial Go set:
  - `iferr`  → `if err != nil {\n\t${1:return err}\n}`
  - `main`   → `func main() {\n\t${1:}\n}`
  - `struct` → `type ${1:Name} struct {\n\t${2}\n}`
  - `iface`  → `type ${1:Name} interface {\n\t${2}\n}`
  - (Note: gopls does **not** provide snippet completions such as `iferr` —
    those ship with the vscode-go extension, not gopls. Verified against the
    gopls settings doc, which exposes no snippet feature, and by direct gopls
    probes returning zero items for the `iferr`/`forr` prefixes. Hence a custom
    `iferr` snippet is required.)
- Precompute a completion-item template per snippet at module load:
  `{ word = trig, abbr = trig, menu = "[snip]", user_data = vim.json.encode({ snip = body, trig = trig }) }`
  so JSON encoding happens once, not per keystroke.
- Patch `vim.fn.complete` once (idempotent guard):
  - If `vim.bo.filetype` has no snippets, delegate immediately (zero overhead for
    other buffers).
  - Otherwise: strip any previously injected items from the incoming `matches`
    (detected via `user_data` containing the `snip` marker — prevents duplicates
    when the LSP handler merges `complete_info()` items on refresh), derive the
    typed prefix from `start_col` + cursor, append matching snippet items, then
    call the original `vim.fn.complete`.
- `CompleteDone` autocmd: if `vim.v.completed_item.user_data` decodes to a
  `{ snip, trig }` marker, delete the just-inserted trigger word
  (`nvim_buf_set_text` from `col - #word` to `col`), place the cursor at the
  start, and `vim.snippet.expand(snip)`.
- `require "snippets"` added to `init.lua` after the other modules.

### 3. Placeholder navigation (`dot_config/nvim/lua/keymaps.lua`)

Add insert/select-mode `expr` keymaps:
- `<Tab>`: `vim.snippet.jump(1)` when `vim.snippet.active({ direction = 1 })`, else literal `<Tab>`.
- `<S-Tab>`: `vim.snippet.jump(-1)` when `vim.snippet.active({ direction = -1 })`, else literal `<S-Tab>`.

## Cross-platform & performance

- All Lua code is platform-agnostic (no paths, no shell, no OS-specific APIs);
  identical source deploys on Linux/Windows/Termux via chezmoi.
- Dropping `<C-Space>` also avoids IME/keyboard conflicts on Windows.
- Performance:
  - Completion-item templates precomputed once.
  - Injection is filetype-gated with a nil-check before any list work; per-call
    cost is a linear dedup + append over a tiny list.
  - Curated trigger set + native adaptive debounce; no per-keystroke JSON work.
- Limitation (documented, accepted): snippets ride on the LSP completion path, so
  on Termux without gopls they do not appear. gopls attach is already gated by
  `vim.fn.executable("gopls")` in `lsp.lua`.

## Verification

Headless-verified (this environment, nvim v0.12.4):
- `vim.snippet` expand/jump/`$0` lifecycle.
- `vim.fn.complete` monkeypatch intercepts and appends items.
- `CompleteDone` expansion function: deletes trigger, expands body, focuses first
  placeholder, `<Tab>`-jump exits at `$0`.
- gopls v0.23.0 attaches; `triggerCharacters = ["."]` confirmed.
- Native `vim.lsp.completion.enable` + `get()` API presence.

Manual (user machine) — the live popup interaction requires insert mode, which
cannot be driven headless:
1. `nvim --headless -u <config> +'edit main.go' +'lua vim.wait(1000); print(#vim.lsp.get_clients())' +qa`
   — confirm gopls attaches.
2. In a Go file, type `mai` and confirm the `main` snippet appears in the menu;
   select it (`<C-y>`) and confirm expansion + `<Tab>` placeholder jumping.
3. Confirm typing `.` (e.g. `u.`) still brings up gopls field completions on-type.

## Files touched

- `dot_config/nvim/lua/snippets.lua` (new)
- `dot_config/nvim/lua/lsp.lua` (on-type enable, remove `<C-Space>` mapping)
- `dot_config/nvim/lua/keymaps.lua` (Tab/S-Tab placeholder jumps)
- `dot_config/nvim/init.lua` (`require "snippets"`)

## Out of scope

- More filetypes/languages (table is extensible).
- `completeopt` `popup` (resolve preview) — optional later.
- Manual completion trigger re-instatement (can be added later as one line).
