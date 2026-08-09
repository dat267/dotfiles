# Remove Custom Snippets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the custom snippet system so completion is gopls-only, keeping on-type autocomplete (trigger-char extension inlined into `lsp.lua`).

**Architecture:** Inline `merge_trigger_chars` into `lsp.lua` first (so removing the module doesn't break on-type), then delete `snippets.lua` and the `init.lua` require. No new modules, no dead code.

**Tech Stack:** Neovim >= 0.11 (verified on v0.12.4), `vim.lsp.completion`.

## Global Constraints

- Zero-plugin; pure Lua; cross-platform (Linux/Windows/Termux).
- Keep on-type autotrigger, trigger-char extension, and `<BS>`/`<Del>`/`<Left>`/`<Right>` re-trigger keymaps.
- No stub/dead code left behind ("leave snippets open" = don't add barriers, not add placeholders).
- Tests: throwaway headless scripts in `/tmp/opencode/`, nvim 0.12.4, rtp prefix `--cmd 'set rtp^=/workspace/dot_config/nvim'`.

---

### Task 1: Inline `merge_trigger_chars` into `lsp.lua`

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/lsp.lua` (LspAttach block, currently `require("snippets").merge_trigger_chars(...)` at line 129)

**Interfaces:**
- Consumes: `vim.tbl_get(client.server_capabilities, "completionProvider")`.
- Produces: local `merge_trigger_chars(server_chars: string[]): string[]` (dedup union of server chars + `a-zA-Z0-9_`); used only in the LspAttach completion block.

- [ ] **Step 1: Run the existing on-type test to confirm it passes now**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_lsp.lua 2>&1 | grep -E "OK|assert"
```

Expected: `test_lsp OK`.

- [ ] **Step 2: Modify `lsp.lua`**

Replace this block (currently lines ~125-131):

```lua
    if client and client:supports_method("textDocument/completion") then
      local provider = vim.tbl_get(client.server_capabilities, "completionProvider")
      if provider then
        provider.triggerCharacters = require("snippets").merge_trigger_chars(provider.triggerCharacters)
        vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })
      end
    end
```

with:

```lua
    -- On-type completion (native, no plugin): extend the server's trigger
    -- characters with identifier characters so the menu appears as you type,
    -- then enable autotrigger. gopls ships only ".", so without extension
    -- on-type would never fire for identifiers.
    local function merge_trigger_chars(server_chars)
      local set = {}
      for _, c in ipairs(server_chars or {}) do
        set[c] = true
      end
      for c in ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"):gmatch(".") do
        set[c] = true
      end
      local out = {}
      for c in pairs(set) do
        out[#out + 1] = c
      end
      return out
    end
    if client and client:supports_method("textDocument/completion") then
      local provider = vim.tbl_get(client.server_capabilities, "completionProvider")
      if provider then
        provider.triggerCharacters = merge_trigger_chars(provider.triggerCharacters)
        vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })
      end
    end
```

- [ ] **Step 3: Run the on-type test to verify it still passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_lsp.lua 2>&1 | grep -E "OK|assert"
```

Expected: `test_lsp OK`.

- [ ] **Step 4: Commit**

```bash
git add dot_config/nvim/lua/lsp.lua
git commit -m "refactor(nvim): inline trigger-char extension into lsp.lua"
```

---

### Task 2: Remove the snippet module

**Files:**
- Delete: `/workspace/dot_config/nvim/lua/snippets.lua`
- Modify: `/workspace/dot_config/nvim/init.lua`

**Interfaces:**
- Consumes: nothing (removes `require("snippets").setup()`).
- Produces: zero `snippets` references in `dot_config/nvim/`; `vim.fn.complete` unpatched.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_no_snippets.lua`:

```lua
require "lsp"
require "options"

-- vim.fn.complete must be unpatched: no snippets CompleteDone autocmd, and
-- complete() must behave as the native function (E785 in normal mode with the
-- unmodified function).
local ac = vim.api.nvim_get_autocmds({ event = "CompleteDone" })
assert(#ac == 0, "no CompleteDone autocmd from snippets, got " .. #ac)

local buf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_set_current_buf(buf)
vim.bo[buf].filetype = "go"
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "mai" })
vim.api.nvim_win_set_cursor(0, { 1, 3 })
-- native complete() raises E785 when called outside insert mode
local ok, err = pcall(vim.fn.complete, 1, { { word = "mainx", menu = "[gopls]" } })
assert(ok == false and tostring(err):match("E785"), "complete() native behavior, got: " .. tostring(err))

-- snippets module must not exist
local s_ok = pcall(require, "snippets")
assert(s_ok == false, "snippets module must not exist")

print("test_no_snippets OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_no_snippets.lua
```

Expected: FAIL — either `require("snippets")` succeeds (module still present) or the `CompleteDone` assertion fails (autocmd still registered).

- [ ] **Step 3: Delete `snippets.lua` and remove the require from `init.lua`**

```bash
git rm dot_config/nvim/lua/snippets.lua
```

Edit `/workspace/dot_config/nvim/init.lua`: delete the line `require("snippets").setup()`, leaving:

```lua
require "comments"
require "format"
require "lsp"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_no_snippets.lua
```

Expected: prints `test_no_snippets OK`, exit 0.

- [ ] **Step 5: Verify no references remain and config loads**

```bash
grep -rn "snippets" dot_config/nvim/ || echo "no snippets references"
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa
```

Expected: `no snippets references`, then `ok`.

- [ ] **Step 6: Run the remaining regression suite**

```bash
for t in test_lsp test_keymaps test_whichwrap test_inlay_hints test_gopls_settings; do
  echo -n "$t: "; nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/$t.lua 2>&1 | grep -oE "(test_[a-z_]+ OK|E5113.*)" | head -1
done
```

Expected: each prints its `OK`. (`test_snippets`, `test_retrigger`, `test_gopls_settings`-adjacent snippet tests are removed/dropped — `test_retrigger` covers the remaining re-trigger keymaps; `test_snippets`/`test_gopls_settings` no longer apply.)

- [ ] **Step 7: Commit**

```bash
git add -A dot_config/nvim
git commit -m "refactor(nvim): remove custom snippet system"
```

---

## Self-Review Notes

- **Spec coverage:** inline trigger merge (T1), delete module + init require + no-refs + unpatched complete (T2). Kept items (autotrigger, retrigger keymaps, whichwrap, inlay toggle) untouched.
- **Placeholder scan:** all steps concrete.
- **Type consistency:** `merge_trigger_chars(string[]) -> string[]` name/signature preserved from the old module so behavior is identical.
