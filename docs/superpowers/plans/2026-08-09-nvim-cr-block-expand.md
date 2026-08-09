# Neovim `{}` Block Expansion on `<CR>` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand an empty auto-paired `{}` into a three-line block with the cursor centered/indented when `<CR>` is pressed in insert mode.

**Architecture:** One insert-mode `<CR>` keymap in `brackets.lua`. Uses the existing `char_before_cursor`/`char_after_cursor` helpers, `nvim_buf_set_text` for the expansion, and a `<C-o>:call cursor()` feed for reliable insert-mode cursor placement.

**Tech Stack:** Neovim >= 0.11 (verified on v0.12.4), `vim.api.nvim_buf_set_text`, `vim.api.nvim_feedkeys`.

## Global Constraints

- Zero-plugin; pure Lua; cross-platform.
- `{` only — `(`/`[` keep native `<CR>`.
- Respect `expandtab`/`shiftwidth` for the middle-line indent; `}` aligns to the current line's leading whitespace.
- Preserve existing `brackets.lua` behavior (auto-pair, smart `<BS>`, `<Tab>` jump-out).
- Tests: throwaway headless scripts in `/tmp/opencode/`, nvim 0.12.4, rtp prefix `--cmd 'set rtp^=/workspace/dot_config/nvim'`.

---

### Task 1: Add the `<CR>` block-expansion keymap

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/brackets.lua` (append after the visual-wrap block, before `return M`)

**Interfaces:**
- Consumes: `char_before_cursor()`, `char_after_cursor()` (already in brackets.lua).
- Produces: insert-mode `<CR>` mapping that expands `{}` and falls through otherwise.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_cr_expand.lua`:

```lua
require "brackets"

-- find the <CR> mapping callback
local cr_cb
for _, m in ipairs(vim.api.nvim_get_keymap("i")) do
  if m.lhs == "<CR>" then cr_cb = m.callback end
end
assert(cr_cb, "<CR> insert mapping present")

local buf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_set_current_buf(buf)
vim.bo[buf].expandtab = true
vim.bo[buf].shiftwidth = 4

-- empty pair at top level
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "func main() {}", "" })
vim.api.nvim_win_set_cursor(0, { 1, 14 }) -- between the braces (on '}')
cr_cb()
vim.wait(50)
local lines = vim.api.nvim_buf_get_lines(buf, 0, 4, false)
assert(table.concat(lines, "\n") == "func main() {\n    \n}\n",
  "expanded: " .. table.concat(lines, "\n"))
local cur = vim.api.nvim_win_get_cursor(0)
assert(cur[1] == 2 and cur[2] == 4, "cursor on middle line at indent end, got " .. vim.inspect(cur))

-- trailing content preserved: "{};" -> "};"
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "if x {}", "" })
vim.api.nvim_win_set_cursor(0, { 1, 6 })
cr_cb()
vim.wait(50)
lines = vim.api.nvim_buf_get_lines(buf, 0, 4, false)
assert(lines[1] == "if x {" and lines[3] == "};", "trailing ; preserved: " .. table.concat(lines, "\n"))

-- non-pair fallthrough: cursor not inside braces -> no expansion
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "abc", "" })
vim.api.nvim_win_set_cursor(0, { 1, 3 })
cr_cb()
vim.wait(50)
lines = vim.api.nvim_buf_get_lines(buf, 0, 2, false)
assert(lines[1] == "abc", "non-pair line unchanged")

print("test_cr_expand OK")
```

Note: `cr_cb()` invokes the mapping function directly. The `<CR>`-feeding fallback path is wrapped so it does not error in normal mode; the expansion branch is fully asserted.

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_cr_expand.lua
```

Expected: FAIL — `cr_cb` is nil (no `<CR>` mapping yet).

- [ ] **Step 3: Append the keymap to `brackets.lua`**

Before `return M`:

```lua
-- <CR> inside an empty auto-paired {} expands into a block with the cursor
-- centered on an indented line. Any other <CR> falls through unchanged.
vim.keymap.set("i", "<CR>", function()
  if not (char_before_cursor() == "{" and char_after_cursor() == "}") then
    vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<CR>", true, false, true), "in", false)
    return
  end
  local row, col = unpack(vim.api.nvim_win_get_cursor(0))
  local line = vim.api.nvim_get_current_line()
  local base_indent = line:match("^%s*") or ""
  local indent_unit = vim.bo.expandtab and string.rep(" ", vim.fn.shiftwidth()) or "\t"
  local middle = base_indent .. indent_unit
  vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col + 1, { "", middle, base_indent .. "}" })
  vim.api.nvim_feedkeys(
    vim.api.nvim_replace_termcodes(("<C-o>:call cursor(%d, %d)<CR>"):format(row + 1, #middle + 1), true, false, true),
    "in",
    false
  )
end, { desc = "expand {} block on <CR>" })
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_cr_expand.lua
```

Expected: prints `test_cr_expand OK`, exit 0.

- [ ] **Step 5: Run the config smoke check**

```bash
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa
```

Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add dot_config/nvim/lua/brackets.lua
git commit -m "feat(nvim): expand {} block with centered cursor on <CR>"
```

---

### Task 2: Regression + manual check

- [ ] **Step 1: Run the remaining regression suite**

```bash
for t in test_lsp test_retrigger test_keymaps test_whichwrap test_inlay_hints test_gopls_settings; do
  echo -n "$t: "; nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/$t.lua 2>&1 | grep -oE "(test_[a-z_]+ OK|E5113.*)" | head -1
done
```

Expected: each prints its `OK`.

- [ ] **Step 2: Manual check (user machine)**

After `chezmoi apply`: in a Go file, type `{` (auto-pairs to `{}`), then press
`<CR>` — expect the three-line block with the cursor centered and indented.
Type `(` / `[` + `<CR>` — expect normal newline (no expansion).

---

## Self-Review Notes

- **Spec coverage:** expansion behavior + trailing-content preservation + fallthrough (T1 test), cursor-on-middle-line (T1), scope `{`-only (T1 code guards on `{`/`}`), regression + manual (T2).
- **Placeholder scan:** all steps concrete.
- **Type consistency:** uses existing `char_before_cursor`/`char_after_cursor`; `<CR>` keymap desc `"expand {} block on <CR>"`.
