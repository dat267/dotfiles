# Neovim Safe Autocompletion Load Trim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce LSP/render load of on-type autocompletion via two safe changes to `dot_config/nvim/lua/lsp.lua` — disable gopls postfix completions and hide inlay hints during insert mode.

**Architecture:** Both changes are pure config edits to `lsp.lua`: one gopls setting under `settings.gopls`, and a pair of `InsertEnter`/`InsertLeave` autocmds that toggle `vim.lsp.inlay_hint.enable(false/true)`. No new modules, no behavior trade-offs (matcher stays Fuzzy, staticcheck stays on, function-call completion stays on).

**Tech Stack:** Neovim >= 0.11 (verified on v0.12.4), `vim.lsp`, `vim.lsp.inlay_hint`.

## Global Constraints

- Zero-plugin: built-in APIs only.
- Cross-platform: pure Lua, no OS-specific paths/shells — works on Linux/Windows/Termux.
- Do NOT touch `matcher`, `staticcheck`, `completeFunctionCalls`, or the retrigger debounce (explicitly declined in the spec).
- Preserve existing gopls settings (`analyses`, `staticcheck = true`, `gofumpt = true`).
- Tests are throwaway headless scripts in `/tmp/opencode/` (AGENTS.md convention), run against the source config with nvim 0.12.4 at `/home/opencode/.local/bin/nvim` and rtp prefix `--cmd 'set rtp^=/workspace/dot_config/nvim'`.

---

### Task 1: gopls — disable postfix completions

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/lsp.lua` (gopls `settings.gopls` table, lines 8-14)
- Test: `/tmp/opencode/test_gopls_settings.lua`

**Interfaces:**
- Consumes: existing `vim.lsp.config("gopls", ...)` call.
- Produces: gopls config with `settings.gopls.experimentalPostfixCompletions == false`; `staticcheck` and `gofumpt` unchanged.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_gopls_settings.lua`:

```lua
require "lsp"

local cfg = vim.lsp.config("gopls")
assert(cfg, "gopls config exists")
local settings = cfg and cfg.settings and cfg.settings.gopls
assert(settings, "gopls settings present")
assert(
  settings.experimentalPostfixCompletions == false,
  "experimentalPostfixCompletions=false, got " .. tostring(settings.experimentalPostfixCompletions)
)
assert(settings.staticcheck == true, "staticcheck untouched")
assert(settings.gofumpt == true, "gofumpt untouched")
assert(settings.matcher == nil, "matcher untouched (fuzzy default)")

print("test_gopls_settings OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_gopls_settings.lua
```

Expected: FAIL on the `experimentalPostfixCompletions` assertion (currently `nil`).

- [ ] **Step 3: Modify `/workspace/dot_config/nvim/lua/lsp.lua`**

In the `gopls` config's `settings.gopls` table, add one line:

```lua
  gopls = {
    settings = {
      gopls = {
        analyses = { unusedparams = true, unusedwrite = true },
        staticcheck = true,
        gofumpt = true,
        experimentalPostfixCompletions = false,
      },
    },
  },
```

(The diff is: add `experimentalPostfixCompletions = false,` after `gofumpt = true,`.)

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_gopls_settings.lua
```

Expected: prints `test_gopls_settings OK`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add dot_config/nvim/lua/lsp.lua
git commit -m "perf(nvim): disable gopls postfix completions"
```

---

### Task 2: hide inlay hints during insert mode

**Files:**
- Modify: `/workspace/dot_config/nvim/lua/lsp.lua` (around the existing `vim.lsp.inlay_hint.enable(true, nil)` at line 138)
- Test: `/tmp/opencode/test_inlay_hints.lua`

**Interfaces:**
- Consumes: `vim.lsp.inlay_hint.enable(bool)` / `vim.lsp.inlay_hint.is_enabled()` (global; verified present in v0.12.4).
- Produces: a named augroup `nvim.lsp.inlay_hints` with `InsertEnter` → disable and `InsertLeave` → enable callbacks. Hints are on by default (module load), off while inserting, restored on leave.

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_inlay_hints.lua`:

```lua
require "lsp"

local function callbacks(event)
  local out = {}
  for _, a in ipairs(vim.api.nvim_get_autocmds({ event = event })) do
    if a.group == "nvim.lsp.inlay_hints" then
      out[#out + 1] = a.callback
    end
  end
  return out
end

local enter = callbacks("InsertEnter")
local leave = callbacks("InsertLeave")
assert(#enter == 1, "InsertEnter autocmd registered, got " .. #enter)
assert(#leave == 1, "InsertLeave autocmd registered, got " .. #leave)

assert(vim.lsp.inlay_hint.is_enabled(), "hints enabled by default")
enter[1]()
assert(not vim.lsp.inlay_hint.is_enabled(), "hints disabled on InsertEnter")
leave[1]()
assert(vim.lsp.inlay_hint.is_enabled(), "hints re-enabled on InsertLeave")

print("test_inlay_hints OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_inlay_hints.lua
```

Expected: FAIL — `#enter == 0` (no `nvim.lsp.inlay_hints` augroup exists yet).

- [ ] **Step 3: Modify `/workspace/dot_config/nvim/lua/lsp.lua`**

Replace the existing `-- Inlay hints on by default` block:

```lua
-- Inlay hints on by default
vim.lsp.inlay_hint.enable(true, nil)
```

with:

```lua
-- Inlay hints on by default, but hidden while typing: they otherwise refresh
-- on every text change during insert, adding per-keystroke render + recompute
-- load. Re-enabled on leaving insert mode.
vim.lsp.inlay_hint.enable(true, nil)
local inlay_augroup = vim.api.nvim_create_augroup("nvim.lsp.inlay_hints", { clear = true })
vim.api.nvim_create_autocmd("InsertEnter", {
  group = inlay_augroup,
  callback = function()
    vim.lsp.inlay_hint.enable(false)
  end,
})
vim.api.nvim_create_autocmd("InsertLeave", {
  group = inlay_augroup,
  callback = function()
    vim.lsp.inlay_hint.enable(true)
  end,
})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/test_inlay_hints.lua
```

Expected: prints `test_inlay_hints OK`, exit 0.

- [ ] **Step 5: Run the config smoke check**

```bash
nvim --headless --cmd 'set rtp^=/workspace/dot_config/nvim' -u /workspace/dot_config/nvim/init.lua +'lua print("ok")' +qa
```

Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add dot_config/nvim/lua/lsp.lua
git commit -m "perf(nvim): hide inlay hints while inserting"
```

---

### Task 3: Regression + manual check

- [ ] **Step 1: Run the existing autocompletion test suite** (regression guard)

```bash
for t in test_snippets test_retrigger test_lsp test_keymaps; do
  echo "--- $t ---"
  nvim --headless -u NONE --cmd 'set rtp^=/workspace/dot_config/nvim' -l /tmp/opencode/$t.lua 2>&1 | grep -E "OK|Error|assert" | head -3
done
```

Expected: each prints its `OK` line (gopls `InlayHint` stderr noise is benign).

- [ ] **Step 2: Verify gopls accepts the new setting (best-effort)**

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":null,"rootUri":"file:///tmp/opencode","capabilities":{},"workspaceFolders":[]}}\r\n' | timeout 20 env PATH=/home/opencode/.local/go/bin:$PATH gopls -mode=stdio 2>&1 | head -c 300
```

Then send a `workspace/didChangeConfiguration` with `{"settings":{"gopls":{"experimentalPostfixCompletions":false}}}` and confirm gopls does not log an "unknown setting" error. (Container gopls is otherwise unreliable for completion, so this is best-effort: the setting name is verified against the gopls settings doc.)

- [ ] **Step 3: Manual check (user machine)**

After `chezmoi apply`: in a `.go` file, confirm typing still completes on-type; postfix completions no longer appear (or were never noticed); inlay hints disappear while typing and return on `<Esc>`.

---

## Self-Review Notes

- **Spec coverage:** gopls postfix setting (T1), inlay-hint insert toggle (T2), regression + smoke + manual (T3). Declined items (matcher/staticcheck/completeFunctionCalls/retrigger) untouched — asserted in T1 test.
- **Placeholder scan:** all steps contain concrete code/commands.
- **Type consistency:** augroup name `nvim.lsp.inlay_hints` used identically in T2 test and implementation; `vim.lsp.inlay_hint.enable/is_enabled` verified on v0.12.4.
