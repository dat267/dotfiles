# Neovim Line-Boundary Cursor Wrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `whichwrap` flags so `h`/`l` and arrow keys wrap the cursor across line boundaries.

**Architecture:** A single option append in `dot_config/nvim/lua/options.lua`. No new modules.

**Tech Stack:** Neovim >= 0.11 (verified on v0.12.4), `vim.opt` / `whichwrap`.

## Global Constraints

- Zero-plugin: built-in option only.
- Cross-platform: `whichwrap` is a core option — identical on Linux/Windows/Termux.
- Preserve existing `whichwrap` defaults (`b,s`).
- Test via headless nvim 0.12.4 with rtp prefix `--cmd 'set rtp^=/workspace/dot_config/nvim'`.

---

### Task 1: Enable line-boundary cursor wrap

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/options.lua` (options block)
- Test: `/tmp/opencode/test_whichwrap.lua`

**Interfaces:**
- Produces: `vim.o.whichwrap == "b,s,h,l,<,>,[,]"` after loading `options`.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_whichwrap.lua`:

```lua
require "options"

assert(vim.o.whichwrap == "b,s,h,l,<,>,[,]", "whichwrap got: " .. vim.o.whichwrap)
assert(vim.o.whichwrap:find("h"), "h wraps")
assert(vim.o.whichwrap:find("l"), "l wraps")
assert(vim.o.whichwrap:find("<"), "< wraps")
assert(vim.o.whichwrap:find(">"), "> wraps")
assert(vim.o.whichwrap:find("%["), "[ wraps (insert left)")
assert(vim.o.whichwrap:find("%]"), "] wraps (insert right)")

-- behavior: h at line start moves to previous line end
local buf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_set_current_buf(buf)
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "abc", "def" })
vim.api.nvim_win_set_cursor(0, { 1, 0 })
vim.cmd("normal! h")
assert(vim.api.nvim_win_get_cursor(0)[1] == 2, "h wrapped to previous line, got row " .. vim.api.nvim_win_get_cursor(0)[1])
assert(vim.api.nvim_win_get_cursor(0)[2] == 3, "h landed at previous line end, got col " .. vim.api.nvim_win_get_cursor(0)[2])

-- behavior: l at line end moves to next line start
vim.api.nvim_win_set_cursor(0, { 2, 3 })
vim.cmd("normal! l")
assert(vim.api.nvim_win_get_cursor(0)[1] == 1, "l wrapped to next line, got row " .. vim.api.nvim_win_get_cursor(0)[1])
assert(vim.api.nvim_win_get_cursor(0)[2] == 0, "l landed at next line start, got col " .. vim.api.nvim_win_get_cursor(0)[2])

print("test_whichwrap OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_whichwrap.lua
```

Expected: FAIL on the `whichwrap` assertion (currently `b,s`), and the `h`/`l` behavior asserts fail (no wrap without `h,l`).

- [ ] **Step 3: Modify `/workspace/dot_config/nvim/lua/options.lua`**

In the options block (after `opt.whichwrap` is unset / anywhere among the `opt.*` lines), add:

```lua
-- Wrap the cursor across line boundaries with h/l and arrow keys
opt.whichwrap:append("h,l,<,>,[,]")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_whichwrap.lua
```

Expected: prints `test_whichwrap OK`, exit 0.

- [ ] **Step 5: Run the config smoke check**

```bash
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa
```

Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add dot_config/nvim/lua/options.lua
git commit -m "feat(nvim): wrap cursor across line boundaries (whichwrap)"
```

---

## Self-Review Notes

- **Spec coverage:** the `whichwrap` append (T1) and behavior verification (T1 test). Interaction note (retrigger keymaps) needs no code change.
- **Placeholder scan:** all steps concrete.
- **Type consistency:** option value `"b,s,h,l,<,>,[,]"` asserted in test matches the implementation.
