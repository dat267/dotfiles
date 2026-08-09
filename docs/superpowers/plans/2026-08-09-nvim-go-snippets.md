# Neovim Zero-Plugin Go Snippets + On-Type Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Go snippets that appear in the LSP completion menu and switch LSP completion to automatic on-type (replacing `<C-Space>`), using only Neovim 0.11+ built-ins.

**Architecture:** A new `lua/snippets.lua` module defines per-filetype snippet templates, patches `vim.fn.complete` to inject snippet items into the LSP completion list, and expands them on `CompleteDone` via `vim.snippet.expand`. `lua/lsp.lua` enables native `vim.lsp.completion` autotrigger with extended trigger characters. `lua/keymaps.lua` adds `<Tab>`/`<S-Tab>` placeholder navigation.

**Tech Stack:** Neovim >= 0.11 (verified on v0.12.4), Lua, `vim.snippet`, `vim.lsp.completion`. gopls for Go completion.

## Global Constraints

- Config is **zero-plugin** — use only built-in APIs (`vim.lsp`, `vim.snippet`, `vim.api`). No external Lua/npm/pip dependencies.
- Cross-platform: pure Lua only — no OS-specific paths, shells, or APIs. Must work on Linux, Windows, Android/Termux.
- Trigger set is identifier chars + the server's own triggers only (NOT all 32–126 printable chars) for performance.
- All `%s`-style / template whitespace rules from AGENTS.md apply; preserve `{{- -}}` trimming (not relevant here, no `.tmpl`).
- Tests run against the **source config** at `/workspace/dot_config/nvim` with nvim v0.12.4 installed at `/home/opencode/.local/bin/nvim` (on PATH). Test scripts live in `/tmp/opencode/` (AGENTS.md: test files must be inside the workspace or `/tmp/opencode/`); they are verification scripts, not committed.
- Every nvim test uses the rtp prefix `--cmd 'set rtp^=/workspace/dot_config/nvim'` so `require "snippets"` / `require "lsp"` resolve.
- The live completion popup (insert-mode feedkeys) **cannot** be driven headless (AGENTS.md gotcha). Unit-test all pure logic; verify the popup manually on the user machine (commands in each task's "Manual check").

---

### Task 1: `lua/snippets.lua` — snippet module

**Files:**
- Create: `/workspace/dot_config/nvim/lua/snippets.lua`
- Test: `/tmp/opencode/test_snippets.lua`

**Interfaces:**
- Consumes: nothing (standalone module).
- Produces (used by later tasks):
  - `M.merge_trigger_chars(server_chars: string[]): string[]` — dedup union of server chars + identifier chars `a-z A-Z 0-9 _`.
  - `M.merge_items(matches: table[], start_col: number): table[]` — strips previously injected items (`menu == "[snip]"`), appends snippet items whose trigger is prefixed by the typed text (derived from `start_col` + cursor on the current line). Returns `matches` unchanged for filetypes with no snippets.
  - `M.expand_completed(item: table): boolean` — if `item.user_data` decodes to `{ snip = <body>, trig = <trigger> }`, deletes `#item.word` chars before the cursor and calls `vim.snippet.expand(body)`; returns `true` on success, `false` otherwise.
  - `M.setup()` — idempotent; patches `vim.fn.complete` (calls `merge_items`, then delegates) and registers a `CompleteDone` autocmd calling `expand_completed(vim.v.completed_item)`.

**Snippet definitions** (LSP snippet syntax; verified to expand with `vim.snippet`):

```lua
local snippets = {
  go = {
    { trig = "main",   body = "func main() {\n\t${1:}\n}\n", desc = "main function" },
    { trig = "struct", body = "type ${1:Name} struct {\n\t${2}\n}\n", desc = "struct type" },
    { trig = "iface",  body = "type ${1:Name} interface {\n\t${2}\n}\n", desc = "interface type" },
  },
}
```

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_snippets.lua`:

```lua
local snippets = require "snippets"

-- merge_trigger_chars
local merged = snippets.merge_trigger_chars({ "." })
assert(vim.list_contains(merged, "."), "server trigger preserved")
assert(vim.list_contains(merged, "a"), "lowercase added")
assert(vim.list_contains(merged, "Z"), "uppercase added")
assert(vim.list_contains(merged, "9"), "digit added")
assert(vim.list_contains(merged, "_"), "underscore added")
assert(not vim.list_contains(merged, " "), "space NOT added")

-- merge_items: prefix filter + dedup of already-injected items
local buf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_set_current_buf(buf)
vim.bo[buf].filetype = "go"
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "mai" })
vim.api.nvim_win_set_cursor(0, { 1, 3 })

local injected = { word = "main", menu = "[snip]", user_data = vim.json.encode({ snip = "x", trig = "main" }) }
local lsp_item = { word = "mainx", menu = "[lsp]" }
local out = snippets.merge_items({ lsp_item, injected }, 1)
assert(#out == 2, "injected dup stripped then re-added: got " .. #out)
local snip_found = false
for _, m in ipairs(out) do
  if m.menu == "[snip]" then snip_found = true end
end
assert(snip_found, "snippet item appended to list")
assert(out[1].word == "mainx", "non-snippet item kept first")

-- merge_items: non-go filetype returns list unchanged
vim.bo[buf].filetype = "lua"
local untouched = snippets.merge_items({ { word = "a" } }, 1)
assert(#untouched == 1 and untouched[1].word == "a", "non-go list untouched")

-- merge_items: no match for typed prefix
vim.bo[buf].filetype = "go"
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "zz" })
vim.api.nvim_win_set_cursor(0, { 1, 2 })
local none = snippets.merge_items({}, 1)
assert(#none == 0, "no snippet matches 'zz'")

-- expand_completed
local ebuf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_set_current_buf(ebuf)
vim.bo[ebuf].expandtab = true
vim.bo[ebuf].shiftwidth = 4
vim.api.nvim_buf_set_lines(ebuf, 0, -1, false, { "func x() {", "\tmain", "}" })
vim.api.nvim_win_set_cursor(0, { 2, 5 })
local item = { word = "main", user_data = vim.json.encode({ snip = "func main() {\n\t${1:body}\n}\n", trig = "main" }) }
assert(snippets.expand_completed(item) == true, "expansion returned true")
vim.wait(100)
assert(vim.snippet.active(), "snippet session active after expansion")
local lines = vim.api.nvim_buf_get_lines(ebuf, 0, 3, false)
assert(lines[2]:match("func main%(%) %{"), "body expanded: " .. vim.inspect(lines))
assert(snippets.expand_completed({ word = "x" }) == false, "no-op for non-snippet item")

print("test_snippets OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_snippets.lua
```

Expected: error `module 'snippets' not found` (file does not exist yet).

- [ ] **Step 3: Create `/workspace/dot_config/nvim/lua/snippets.lua`**

```lua
local M = {}

local snippets = {
  go = {
    { trig = "main",   body = "func main() {\n\t${1:}\n}\n",   desc = "main function" },
    { trig = "struct", body = "type ${1:Name} struct {\n\t${2}\n}\n", desc = "struct type" },
    { trig = "iface",  body = "type ${1:Name} interface {\n\t${2}\n}\n", desc = "interface type" },
  },
}

local items = {}
for ft, list in pairs(snippets) do
  items[ft] = {}
  for _, s in ipairs(list) do
    items[ft][s.trig] = {
      word = s.trig,
      abbr = s.trig,
      menu = "[snip]",
      user_data = vim.json.encode({ snip = s.body, trig = s.trig }),
    }
  end
end

local IDENT_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

function M.merge_trigger_chars(server_chars)
  local set = {}
  for _, c in ipairs(server_chars or {}) do
    set[c] = true
  end
  for c in IDENT_CHARS:gmatch(".") do
    set[c] = true
  end
  local out = {}
  for c in pairs(set) do
    out[#out + 1] = c
  end
  return out
end

function M.merge_items(matches, start_col)
  local ft_items = items[vim.bo.filetype]
  if not ft_items then
    return matches
  end
  local cleaned = {}
  for _, m in ipairs(matches) do
    if m.menu ~= "[snip]" then
      cleaned[#cleaned + 1] = m
    end
  end
  local line = vim.api.nvim_get_current_line()
  local cursor_col = vim.api.nvim_win_get_cursor(0)[2]
  local prefix = ""
  if start_col and start_col >= 1 and start_col <= cursor_col + 1 then
    prefix = line:sub(start_col, cursor_col + 1)
  end
  for trig, item in pairs(ft_items) do
    if trig:sub(1, #prefix) == prefix then
      cleaned[#cleaned + 1] = item
    end
  end
  return cleaned
end

function M.expand_completed(item)
  if not item or type(item.user_data) ~= "string" then
    return false
  end
  local ok, ud = pcall(vim.json.decode, item.user_data)
  if not ok or type(ud) ~= "table" or not ud.snip then
    return false
  end
  local row, col = unpack(vim.api.nvim_win_get_cursor(0))
  local word = item.word or ud.trig
  local start = col - #word
  if start < 0 then
    return false
  end
  vim.api.nvim_buf_set_text(0, row - 1, start, row - 1, col, {})
  vim.api.nvim_win_set_cursor(0, { row, start })
  vim.snippet.expand(ud.snip)
  return true
end

function M.setup()
  if M._setup then
    return
  end
  M._setup = true

  local orig = vim.fn.complete
  vim.fn.complete = function(start_col, matches)
    if type(matches) == "table" and items[vim.bo.filetype] then
      matches = M.merge_items(matches, start_col)
    end
    return orig(start_col, matches)
  end

  vim.api.nvim_create_autocmd("CompleteDone", {
    callback = function()
      M.expand_completed(vim.v.completed_item)
    end,
    desc = "expand custom snippets",
  })
end

return M
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_snippets.lua
```

Expected: prints `test_snippets OK`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add dot_config/nvim/lua/snippets.lua
git commit -m "feat(nvim): add zero-plugin snippet engine (go)"
```

---

### Task 2: `lua/lsp.lua` — on-type completion

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/lsp.lua` (LspAttach block, lines 91-125)
- Test: `/tmp/opencode/test_lsp.lua`

**Interfaces:**
- Consumes: `require("snippets").merge_trigger_chars(server_chars)` from Task 1.
- Produces: on attach, sets `client.server_capabilities.completionProvider.triggerCharacters` to the merged set, calls `vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })`, and removes the `<C-Space>` insert mapping.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_lsp.lua`:

```lua
require "lsp"

local buf = vim.api.nvim_create_buf(false, false)
vim.api.nvim_set_current_buf(buf)
vim.bo[buf].path = "/tmp/opencode/main.go"
vim.bo[buf].filetype = "go"
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "package main", "", "func main() {", "}" })

vim.lsp.start({ name = "gopls-snippet-test", cmd = { "gopls" }, root_dir = "/tmp/opencode" }, { bufnr = buf })

local client
for i = 1, 40 do
  vim.wait(500)
  for _, c in ipairs(vim.lsp.get_clients({ bufnr = buf })) do
    if c.name == "gopls-snippet-test" then
      client = c
    end
  end
  if client then break end
end
assert(client, "gopls test client attached")

local triggers = vim.tbl_get(client.server_capabilities, "completionProvider", "triggerCharacters")
assert(triggers, "completionProvider.triggerCharacters present")
assert(vim.list_contains(triggers, "."), "server trigger preserved")
assert(vim.list_contains(triggers, "a"), "lowercase added")
assert(vim.list_contains(triggers, "9"), "digit added")
assert(vim.list_contains(triggers, "_"), "underscore added")
assert(not vim.list_contains(triggers, " "), "space NOT added")

local km = vim.api.nvim_buf_get_keymap(buf, "i")
for _, m in ipairs(km) do
  assert(m.lhs ~= "<C-Space>", "<C-Space> insert mapping must be removed")
end
assert(vim.bo[buf].omnifunc == "v:lua.vim.lsp.omnifunc", "omnifunc preserved as fallback")

print("test_lsp OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_lsp.lua
```

Expected: FAIL on the trigger-character assertions (current lsp.lua does not extend triggers) and on `<C-Space>` (still present).

- [ ] **Step 3: Modify `/workspace/dot_config/nvim/lua/lsp.lua`**

In the `LspAttach` callback (around lines 91-125), make these changes:

1. After `local bufnr = args.buf`, add a client lookup:

```lua
    local client = vim.lsp.get_client_by_id(args.data.client_id)
```

2. Replace the `<C-Space>` omni mapping block (currently lines 119-123):

```lua
    -- Manual omni-completion intellisense (no plugin): <C-Space> in insert
    -- mode triggers LSP completion; <C-n>/<C-p> continue keyword completion.
    vim.keymap.set("i", "<C-Space>", "<C-x><C-o>", { buffer = bufnr, desc = "LSP omni-completion" })

    vim.bo[bufnr].omnifunc = "v:lua.vim.lsp.omnifunc"
```

with:

```lua
    -- On-type completion (native, no plugin): extend the server's trigger
    -- characters with identifier characters so the completion menu appears as
    -- you type, then enable autotrigger. gopls ships only ".", so without
    -- extension on-type would never fire for identifiers. <C-Space> manual
    -- completion was replaced by this; <C-x><C-o> stays available via omnifunc.
    if client and client:supports_method("textDocument/completion") then
      local provider = vim.tbl_get(client.server_capabilities, "completionProvider")
      if provider then
        provider.triggerCharacters = require("snippets").merge_trigger_chars(provider.triggerCharacters)
        vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })
      end
    end

    vim.bo[bufnr].omnifunc = "v:lua.vim.lsp.omnifunc"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_lsp.lua
```

Expected: prints `test_lsp OK`, exit 0. (First run after the change is slow — gopls indexes the module; the test waits up to 20 s for attach.)

- [ ] **Step 5: Commit**

```bash
git add dot_config/nvim/lua/lsp.lua
git commit -m "feat(nvim): on-type LSP completion, drop <C-Space>"
```

---

### Task 3: `lua/keymaps.lua` — snippet placeholder navigation

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/keymaps.lua`
- Test: `/tmp/opencode/test_keymaps.lua`

**Interfaces:**
- Consumes: `vim.snippet.active({ direction = n })` / `vim.snippet.jump(n)` (built-in).
- Produces: insert/select-mode `<Tab>` and `<S-Tab>` expr mappings that jump between snippet placeholders when a snippet is active, else fall through to the literal key.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_keymaps.lua`:

```lua
require "keymaps"

local tab_cb, stab_cb
for _, m in ipairs(vim.api.nvim_buf_get_keymap(0, "i")) do
  if m.lhs == "<Tab>" then tab_cb = m.callback end
  if m.lhs == "<S-Tab>" then stab_cb = m.callback end
end
assert(tab_cb, "<Tab> insert mapping present")
assert(stab_cb, "<S-Tab> insert mapping present")

local buf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_set_current_buf(buf)
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "" })
vim.api.nvim_win_set_cursor(0, { 1, 0 })

assert(tab_cb() == "<Tab>", "Tab falls through when no snippet active")
assert(stab_cb() == "<S-Tab>", "S-Tab falls through when no snippet active")

vim.snippet.expand("${1:a}${2:b}")
vim.wait(100)
assert(vim.snippet.active(), "snippet active")
local t = tab_cb()
local st = stab_cb()
assert(t:match("jump(1)"), "Tab jumps forward when active: " .. tostring(t))
assert(st:match("jump%-1"), "S-Tab jumps back when active: " .. tostring(st))

print("test_keymaps OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_keymaps.lua
```

Expected: FAIL (`tab_cb` is nil — no `<Tab>` mapping in keymaps.lua yet).

- [ ] **Step 3: Append to `/workspace/dot_config/nvim/lua/keymaps.lua`**

```lua
-- Snippet placeholder navigation (vim.snippet; only jumps while a snippet is active)
map({ "i", "s" }, "<Tab>", function()
  if vim.snippet.active({ direction = 1 }) then
    return "<Cmd>lua vim.snippet.jump(1)<CR>"
  end
  return "<Tab>"
end, { expr = true, desc = "next snippet placeholder" })
map({ "i", "s" }, "<S-Tab>", function()
  if vim.snippet.active({ direction = -1 }) then
    return "<Cmd>lua vim.snippet.jump(-1)<CR>"
  end
  return "<S-Tab>"
end, { expr = true, desc = "prev snippet placeholder" })
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_keymaps.lua
```

Expected: prints `test_keymaps OK`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add dot_config/nvim/lua/keymaps.lua
git commit -m "feat(nvim): tab/s-tab snippet placeholder navigation"
```

---

### Task 4: `init.lua` — wire snippets into the config

**Files:**
- Modify: `/workspace/dot_config/nvim/init.lua`
- Test: `/tmp/opencode/assert_full.lua`

**Interfaces:**
- Consumes: `require("snippets").setup()` (Task 1).
- Produces: full config loads cleanly with snippets active.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/assert_full.lua`:

```lua
local ok, err = pcall(require, "snippets")
assert(ok, "snippets requireable: " .. tostring(err))
assert(vim.g.colors_name == "catppuccin", "colorscheme applied, got " .. tostring(vim.g.colors_name))
local ac = vim.api.nvim_get_autocmds({ event = "CompleteDone" })
assert(#ac >= 1, "CompleteDone autocmd registered after init load")
print("assert_full OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua -c 'luafile /tmp/opencode/assert_full.lua' -c 'qa!'
```

Expected: FAIL on the `CompleteDone` assertion (`#ac == 0` — init.lua does not require snippets yet).

- [ ] **Step 3: Modify `/workspace/dot_config/nvim/init.lua`**

Add one line before `require "lsp"`:

```lua
require("snippets").setup()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua -c 'luafile /tmp/opencode/assert_full.lua' -c 'qa!'
```

Expected: prints `assert_full OK`, exit 0.

- [ ] **Step 5: Run the AGENTS.md smoke check**

```bash
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa
```

Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add dot_config/nvim/init.lua
git commit -m "feat(nvim): enable snippet module in config"
```

---

### Task 5: Manual verification on the user machine

The live completion popup requires insert mode, which cannot be driven headless. Verify on the target machine (Linux/Windows/Termux with nvim >= 0.11 and gopls installed):

1. In a `.go` file, type `mai` — the `main` snippet must appear in the completion menu as you type (no `<C-Space>` needed). Press `<C-y>` to select → `func main() { ... }` expands with the cursor on the placeholder line.
2. Press `<Tab>` to jump to the next placeholder / end; `<S-Tab>` moves back.
3. Type `u.` after a struct variable — gopls field completions still appear on-type (`.` is in the merged trigger set).
4. Type `iferr` — gopls's native snippet appears and expands on `<C-y>` (native `vim.lsp.completion` side effects).
5. Confirm the config still loads: `nvim --headless -u ~/.config/nvim/init.lua +'lua print("ok")' +qa`.

---

## Self-Review Notes

- **Spec coverage:** on-type enable (T2), snippets module with dedup/prefix/expand (T1), Tab/S-Tab navigation (T3), init wiring (T4), cross-platform pure-Lua constraint (all tasks), manual popup verification (T5). `iferr` intentionally excluded per spec.
- **Type consistency:** `merge_trigger_chars(string[]) -> string[]`, `merge_items(table[], number) -> table[]`, `expand_completed(table) -> boolean`, `setup()` — identical names/signatures across tasks.
- **Known limitation (accepted, in spec):** snippets only appear where LSP completion fires (gopls attached). On Termux without gopls they do not appear.

---

## Execution Notes (post-implementation corrections)

These reflect the actual implementation and test scripts on disk in `/tmp/opencode/`, which differ from the plan's embedded scripts in the following ways:

1. **Test 1 (`test_snippets.lua`)** — the expansion assertion in the plan used cursor `{2,5}` on line `"\tmain"`; headless nvim clamps end-of-line cursor columns to `len-1` (verified: `{2,5}` → `{2,4}`), which silently made `start = col - #word = 0` and deleted the leading tab — the old assertion passed for the wrong reason. The on-disk test places a sentinel after the trigger (`"\tmainZ"`, cursor col 5), asserts the **full** buffer contents after expansion, and additionally tests: deterministic snippet order (`main,struct,iface`), malformed-body rollback (trigger word restored), and the patched `complete()` delegating unchanged for string lists and empty lists (`E785` in normal mode).
2. **Test 3 (`test_keymaps.lua`)** — the plan queried `nvim_buf_get_keymap(0, "i")`, which returns only buffer-local mappings; `keymaps.lua` registers global ones, so the plan's lookup returned nothing. The on-disk test uses `vim.api.nvim_get_keymap("i")`. Also, `vim.snippet.active({ direction = -1 })` is `false` at the first tabstop (nothing to jump back to), so the plan's "S-Tab jumps immediately after expand" assertion was wrong; the on-disk test first asserts S-Tab falls through at tabstop 1, then jumps forward and asserts S-Tab jumps back at tabstop 2.
3. **Production guard (code review finding):** `setup()`'s `complete()` patch now only merges when `matches` is a non-empty list of dicts (`type(matches[1]) == "table"`), so `vim.snippet` choice tabstops (string lists) and their close call (empty list) are never polluted/reopened by snippet injection.
4. **Snippet bodies** drop the trailing `\n` (e.g. `"func main() {\n\t${1:}\n}"`), avoiding a stray blank line after expansion. Equivalent to the spec's `$0`-terminated bodies (the final cursor sits after the closing brace).
5. **`merge_items` iteration is deterministic** — `items[ft]` is an ordered array (definition order), not a `pairs()` dict, so menu order is stable.
6. **`expand_completed` wraps `vim.snippet.expand` in `pcall`** and restores the trigger word on failure.
7. **`iferr` is included in the Go snippet set.** The original assumption that gopls provides it natively is wrong — verified against the gopls settings doc (no snippet feature exists; only `usePlaceholders`, `matcher`, `experimentalPostfixCompletions`, `completeFunctionCalls`, `completionBudget`) and by direct gopls probes returning `{"isIncomplete":true,"items":[]}` for the `iferr`/`forr` prefixes. Those snippets (`iferr`, `forr`, `fori`, `fpm`…) ship with the vscode-go extension, not gopls.
8. **Re-trigger keymaps added in `lsp.lua` LspAttach** (post-review, from user testing): native autotrigger fires only on `InsertCharPre` (typing), so the popup never returns after backspace/delete or arrow-key movement in insert mode. Buffer-local insert mappings for `<BS>`, `<C-h>`, `<Del>`, `<Left>`, `<Right>` feed the native key (no-remap), then — if the popup is closed and the cursor sits on an identifier — schedule `vim.lsp.completion.get()` behind an 80 ms debounce timer.
9. **Retrigger popup/word state is evaluated inside the 80 ms timer, not synchronously** (fix from user testing): reading `pumvisible()`/cursor right after `nvim_feedkeys` sees the popup as still open while it is mid-close, so the re-trigger was skipped exactly when the key had closed it — the popup flickered on/off across repeated arrow presses. Deferring the check into the timer (after the native key settles) makes the popup consistently reappear while the cursor stays on an identifier.
