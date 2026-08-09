# Design: Safe autocompletion load trim for Neovim

Date: 2026-08-09
Status: Approved

## Goal

Reduce the LSP/rendering load of on-type autocompletion in the Neovim config
(`dot_config/nvim/`) without changing visible behavior. Measured profile (see
below) shows client-side Lua is negligible; the load is LSP request volume,
per-request gopls CPU, background gopls analysis, and per-keystroke inlay-hint
rendering. This spec implements the "safe trim" scope only — no UX-affecting
trade-offs (matcher stays Fuzzy, staticcheck stays on, function-call completion
stays on).

## Changes

### 1. gopls: disable postfix completions (`dot_config/nvim/lua/lsp.lua`)

Add `experimentalPostfixCompletions = false` to the gopls `settings.gopls`
table (currently `analyses`, `staticcheck`, `gofumpt`). gopls computes postfix
completions (e.g. `someSlice.sort!`, `x.append!`) on every completion request;
disabling skips that per-request work. Postfix completions are rarely used, so
the visible effect is minimal. (Setting exists in gopls settings; marked
experimental, so guard acceptance against gopls version.)

### 2. Hide inlay hints during insert mode (`dot_config/nvim/lua/lsp.lua`)

Inlay hints are enabled globally (`vim.lsp.inlay_hint.enable(true, nil)`) and
refresh on text changes, adding per-keystroke render + recompute work while
typing. Add an augroup with:
- `InsertEnter` → `vim.lsp.inlay_hint.enable(false)`
- `InsertLeave` → `vim.lsp.inlay_hint.enable(true)`

Hints disappear on entering insert mode and reappear on leaving. Net: hint
computation/render is suppressed during typing (one disable + one enable
request per insert session, vs. continuous refreshes while typing).

## Not in scope (explicitly declined)

- `matcher` (stays Fuzzy — the biggest per-request CPU lever, but changes
  matching UX).
- `staticcheck` (stays on — biggest background load, but user wants the
  diagnostics).
- `completeFunctionCalls` (stays on).
- Client-side request throttling / retrigger debounce changes.

## Measured baseline (this repo, nvim 0.12.4)

- `snippets.merge_items` (our `vim.fn.complete` patch): ~0.03–0.04 µs/call at
  10–500 result items; non-Go fast path ~0.035 µs. Negligible — no change.
- Dominant load is native autotrigger request volume + gopls per-request cost,
  which these two changes trim.

## Verification

Headless (nvim 0.12.4 at `/home/opencode/.local/bin/nvim`):
1. Config smoke: `nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa`.
2. `vim.lsp.config("gopls")` resolves with `experimentalPostfixCompletions = false` in `settings.gopls`.
3. `InsertEnter`/`InsertLeave` autocmds registered under a named augroup; invoking `InsertLeave` sets `vim.lsp.inlay_hint.is_enabled()` true and `InsertEnter` sets it false.
4. gopls accepts the setting without startup error (container gopls; best-effort — container gopls completion is otherwise unreliable).

Manual (user machine): after `chezmoi apply`, confirm typing still completes as
before, postfix completions are gone (or never noticed), and inlay hints
disappear while typing and return on `<Esc>`.

## Files touched

- `dot_config/nvim/lua/lsp.lua` (gopls settings + inlay-hint augroup)

## Out of scope

- Other languages' settings (pyright/ts_ls/etc. unchanged).
- Any matcher/staticcheck/function-call/retrigger changes.
