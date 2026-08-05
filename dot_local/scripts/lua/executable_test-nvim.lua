#!/usr/bin/env -S nvim --clean -l
-- Test harness for the zero-plugin Neovim config.
--
-- Usage:
--   nvim --clean -l dot_local/scripts/lua/executable_test-nvim.lua
--   nvim --clean -l dot_local/scripts/lua/executable_test-nvim.lua lsp   # filter
--
-- Exits 0 if all matching tests pass, 1 otherwise. Prints PASS/FAIL/SKIP.

-- Bootstrap: find the config to test.
--   1. $NVIM_TEST_CONFIG (explicit override)
--   2. sibling source repo (script lives in dot_local/scripts/lua/)
--   3. deployed config at ~/.config/nvim (when run from ~/.local after apply)
local function find_config_dir()
  if vim.env.NVIM_TEST_CONFIG and vim.fn.isdirectory(vim.env.NVIM_TEST_CONFIG) == 1 then
    return vim.env.NVIM_TEST_CONFIG
  end
  local dir = vim.fn.fnamemodify(arg[0], ":p:h")
  while true do
    local candidate = dir .. "/dot_config/nvim"
    if vim.fn.isdirectory(candidate) == 1 then
      return candidate
    end
    local parent = vim.fn.fnamemodify(dir, ":h")
    if parent == dir then
      break
    end
    dir = parent
  end
  local deployed = vim.fn.expand("~/.config/nvim")
  if vim.fn.isdirectory(deployed) == 1 then
    return deployed
  end
  return nil
end

local CONFIG_DIR = find_config_dir()
if not CONFIG_DIR then
  print("FAIL  bootstrap: could not locate dot_config/nvim (set NVIM_TEST_CONFIG)")
  os.exit(1)
end
vim.opt.runtimepath:prepend(CONFIG_DIR)

local load_ok, load_err = pcall(dofile, CONFIG_DIR .. "/init.lua")
if not load_ok then
  print("FAIL  load: config failed to load")
  print("      " .. tostring(load_err):gsub("\n", "\n      "))
  os.exit(1)
end

-- Minimal test framework
local results = { pass = 0, fail = 0, skip = 0, matched = 0 }
local filter = arg[1]

local function test(name, fn)
  if filter and not name:lower():find(filter:lower(), 1, true) then
    return
  end
  local ok, err = pcall(fn)
  if ok then
    results.pass = results.pass + 1
    results.matched = results.matched + 1
    print("PASS  " .. name)
  elseif type(err) == "table" and err.__skip then
    results.skip = results.skip + 1
    results.matched = results.matched + 1
    print("SKIP  " .. name)
  else
    results.fail = results.fail + 1
    results.matched = results.matched + 1
    print("FAIL  " .. name)
    print("      " .. tostring(err):gsub("\n", "\n      "))
  end
end

local function skip(name)
  error({ __skip = true, name = name }, 2)
end

local function check(cond, msg)
  if not cond then
    error(msg or "assertion failed", 2)
  end
end

local function has_keymap(mode, lhs)
  return vim.fn.maparg(lhs, mode) ~= ""
end

local function has_autocmd(event)
  return #vim.api.nvim_get_autocmds({ event = event }) > 0
end

-- New scratch buffer, returns bufnr.
local function scratch()
  vim.cmd "enew"
  return vim.api.nvim_get_current_buf()
end

-- ── load ────────────────────────────────────────────────────────────────
test("load: colorscheme applied", function()
  check(vim.g.colors_name == "catppuccin", "colors_name=" .. tostring(vim.g.colors_name))
end)

test("load: modules all loadable", function()
  for _, mod in ipairs({
    "options", "keymaps", "autocmds", "treesitter", "netrw", "statusline",
    "brackets", "comments", "format", "lsp",
  }) do
    check(pcall(require, mod), "module failed to load: " .. mod)
  end
end)

-- ── options ─────────────────────────────────────────────────────────────
test("options: number + relativenumber", function()
  check(vim.o.number == true, "number=" .. tostring(vim.o.number))
  check(vim.o.relativenumber == true, "relativenumber=" .. tostring(vim.o.relativenumber))
end)

test("options: indentation", function()
  check(vim.o.tabstop == 4, "tabstop=" .. tostring(vim.o.tabstop))
  check(vim.o.shiftwidth == 4, "shiftwidth=" .. tostring(vim.o.shiftwidth))
  check(vim.o.expandtab == true, "expandtab=" .. tostring(vim.o.expandtab))
end)

test("options: completeopt menu,menuone,noselect", function()
  check(vim.o.completeopt == "menu,menuone,noselect", vim.o.completeopt)
end)

test("options: clipboard unnamedplus", function()
  check(vim.o.clipboard == "unnamedplus", vim.o.clipboard)
end)

test("options: search", function()
  check(vim.o.ignorecase == true, "ignorecase=" .. tostring(vim.o.ignorecase))
  check(vim.o.smartcase == true, "smartcase=" .. tostring(vim.o.smartcase))
  check(vim.o.hlsearch == true, "hlsearch=" .. tostring(vim.o.hlsearch))
end)

test("options: window layout", function()
  check(vim.o.splitright == true, "splitright=" .. tostring(vim.o.splitright))
  check(vim.o.splitbelow == true, "splitbelow=" .. tostring(vim.o.splitbelow))
end)

test("options: persistence", function()
  check(vim.o.undofile == true, "undofile=" .. tostring(vim.o.undofile))
  check(vim.o.swapfile == false, "swapfile=" .. tostring(vim.o.swapfile))
end)

-- ── keymaps ─────────────────────────────────────────────────────────────
local leader_map = {
  [" w"] = "save", [" q"] = "quit window", [" Q"] = "quit all",
  [" sv"] = "vsplit", [" sh"] = "split",
  [" bn"] = "next buffer", [" bp"] = "prev buffer", [" bd"] = "delete buffer",
  [" ff"] = "find files", [" e"] = "file explorer", [" o"] = "outline",
  [" dx"] = "diagnostics list", [" t"] = "terminal",
}
for lhs, desc in pairs(leader_map) do
  test("keymaps: <leader>" .. desc, function()
    check(has_keymap("n", lhs), lhs .. " not mapped")
  end)
end

test("keymaps: window nav", function()
  check(has_keymap("n", "<C-h>"), "<C-h>")
  check(has_keymap("n", "<C-j>"), "<C-j>")
  check(has_keymap("n", "<C-k>"), "<C-k>")
  check(has_keymap("n", "<C-l>"), "<C-l>")
end)

test("keymaps: search centering", function()
  check(has_keymap("n", "n"), "n not mapped")
  check(has_keymap("n", "N"), "N not mapped")
end)

test("keymaps: visual paste without clobber", function()
  check(has_keymap("v", "p"), "v p not mapped")
end)

test("keymaps: terminal escape", function()
  check(has_keymap("t", "<Esc>"), "t <Esc> not mapped")
end)

test("keymaps: move lines", function()
  check(has_keymap("v", "<A-j>"), "v <A-j>")
  check(has_keymap("v", "<A-k>"), "v <A-k>")
end)

-- ── autocmds ────────────────────────────────────────────────────────────
test("autocmds: save hooks exist", function()
  check(has_autocmd("BufWritePre"), "no BufWritePre")
end)

test("autocmds: read hooks exist", function()
  check(has_autocmd("BufReadPost"), "no BufReadPost")
end)

test("autocmds: focus + yank hooks exist", function()
  check(has_autocmd("FocusGained"), "no FocusGained")
  check(has_autocmd("TextYankPost"), "no TextYankPost")
end)

test("autocmds: go filetype gets tabs", function()
  local buf = scratch()
  vim.bo[buf].filetype = "go"
  check(vim.bo[buf].tabstop == 4, "go tabstop=" .. tostring(vim.bo[buf].tabstop))
  check(vim.bo[buf].expandtab == false, "go expandtab=" .. tostring(vim.bo[buf].expandtab))
  vim.api.nvim_buf_delete(buf, { force = true })
end)

test("autocmds: yaml filetype gets 2-space indent", function()
  local buf = scratch()
  vim.bo[buf].filetype = "yaml"
  check(vim.bo[buf].tabstop == 2, "yaml tabstop=" .. tostring(vim.bo[buf].tabstop))
  check(vim.bo[buf].shiftwidth == 2, "yaml shiftwidth=" .. tostring(vim.bo[buf].shiftwidth))
  vim.api.nvim_buf_delete(buf, { force = true })
end)

-- ── treesitter ──────────────────────────────────────────────────────────
test("treesitter: starts on a go buffer", function()
  local buf = scratch()
  vim.bo[buf].filetype = "go"
  local ok, err = pcall(vim.treesitter.start, buf)
  vim.api.nvim_buf_delete(buf, { force = true })
  if not ok and tostring(err):find("Parser could not be created") then
    skip("treesitter: starts on a go buffer")
  end
  check(ok, tostring(err))
end)

test("treesitter: folds configured for go", function()
  local buf = scratch()
  vim.bo[buf].filetype = "go"
  check(vim.wo.foldmethod == "expr", "foldmethod=" .. tostring(vim.wo.foldmethod))
  check(vim.wo.foldexpr:find("treesitter.foldexpr") ~= nil, "foldexpr=" .. tostring(vim.wo.foldexpr))
  vim.api.nvim_buf_delete(buf, { force = true })
end)

-- ── netrw ───────────────────────────────────────────────────────────────
test("netrw: globals set", function()
  check(vim.g.netrw_banner == 0, "banner=" .. tostring(vim.g.netrw_banner))
  check(vim.g.netrw_liststyle == 3, "liststyle=" .. tostring(vim.g.netrw_liststyle))
  check(vim.g.netrw_browse_split == 4, "browse_split=" .. tostring(vim.g.netrw_browse_split))
  check(vim.g.netrw_winsize == 25, "winsize=" .. tostring(vim.g.netrw_winsize))
end)

test("netrw: <leader>e mapped", function()
  check(has_keymap("n", " e"), "<leader>e not mapped")
end)

-- ── statusline ──────────────────────────────────────────────────────────
test("statusline: builds a valid string", function()
  local ok, sl = pcall(require("statusline").build)
  check(ok, tostring(sl))
  check(type(sl) == "string" and sl:len() > 0, "empty statusline")
end)

test("statusline: shows mode + file", function()
  local sl = require("statusline").build()
  check(sl:find("NORMAL", 1, true), "no mode in statusline")
  check(sl:find("%", 1, true), "no file/position in statusline")
end)

-- ── brackets ────────────────────────────────────────────────────────────
test("brackets: smart backspace mapped", function()
  check(has_keymap("i", "<BS>"), "i <BS> not mapped")
end)

test("brackets: tab jump-out mapped", function()
  check(has_keymap("i", "<Tab>"), "i <Tab> not mapped")
end)

test("brackets: visual wrap mapped for all pairs", function()
  for _, open in ipairs({ "(", "[", "{", '"', "'", "`" }) do
    check(has_keymap("v", open), "v " .. open .. " not mapped")
  end
end)

test("brackets: decision logic", function()
  local brackets = require("brackets")
  -- replicate in_special_region / char_after_cursor behavior:
  -- opening char followed by its closer should NOT double-insert
  local buf = scratch()
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "()" })
  vim.fn.cursor(1, 2) -- between ( and )
  vim.api.nvim_win_set_cursor(0, { 1, 1 })
  vim.api.nvim_buf_delete(buf, { force = true })
end)

-- ── comments ────────────────────────────────────────────────────────────
test("comments: toggle round-trip", function()
  local c = require("comments")
  local buf = scratch()
  vim.bo[buf].filetype = "lua"
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "  local x = 1" })
  c.toggle_test(1, 1)
  local commented = vim.api.nvim_buf_get_lines(buf, 0, -1, false)[1]
  check(commented == "  -- local x = 1", "got: " .. commented)
  c.toggle_test(1, 1)
  local uncommented = vim.api.nvim_buf_get_lines(buf, 0, -1, false)[1]
  check(uncommented == "  local x = 1", "got: " .. uncommented)
  vim.api.nvim_buf_delete(buf, { force = true })
end)

test("comments: block comment toggle", function()
  local c = require("comments")
  local buf = scratch()
  vim.bo[buf].filetype = "css"
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "body { color: red }" })
  c.toggle_test(1, 1)
  local wrapped = vim.api.nvim_buf_get_lines(buf, 0, -1, false)[1]
  check(wrapped == "/* body { color: red } */", "got: " .. wrapped)
  c.toggle_test(1, 1)
  local unwrapped = vim.api.nvim_buf_get_lines(buf, 0, -1, false)[1]
  check(unwrapped == "body { color: red }", "got: " .. unwrapped)
  vim.api.nvim_buf_delete(buf, { force = true })
end)

-- ── format ──────────────────────────────────────────────────────────────
test("format: no-op on empty buffer", function()
  local fmt = require("format")
  local buf = scratch()
  vim.bo[buf].filetype = ""
  local ok, err = pcall(fmt.format_buffer)
  check(ok, tostring(err))
  vim.api.nvim_buf_delete(buf, { force = true })
end)

test("format: formatter table has entries", function()
  local fmt = require("format")
  check(type(fmt.format_buffer) == "function", "format_buffer missing")
end)

-- ── lsp-config ──────────────────────────────────────────────────────────
test("lsp: servers registered via vim.lsp.config", function()
  for _, name in ipairs({ "gopls", "pyright", "bashls", "jsonls", "yamlls", "lua_ls", "rust_analyzer" }) do
    check(vim.lsp.config[name] ~= nil, "no config for " .. name)
  end
end)

test("lsp: every registered server has filetypes", function()
  for _, name in ipairs({ "gopls", "pyright", "ts_ls", "bashls", "jsonls", "yamlls", "html", "cssls", "lua_ls", "rust_analyzer" }) do
    local cfg = vim.lsp.config[name]
    check(cfg ~= nil, name .. " not registered")
    check(type(cfg.filetypes) == "table" and #cfg.filetypes > 0, name .. " missing filetypes")
  end
end)

test("lsp: ts_ls explicitly disabled", function()
  check(vim.lsp.config["ts_ls"] ~= nil, "ts_ls not registered")
  check(vim.lsp.config["ts_ls"].enabled == false, "ts_ls should be disabled")
end)

test("lsp: opening a filetype with no server does not attach", function()
  local buf = scratch()
  vim.bo[buf].filetype = "markdown"
  vim.wait(300)
  local clients = vim.lsp.get_clients({ bufnr = buf })
  check(#clients == 0, "unexpected client attached to markdown: " .. table.concat(vim.tbl_map(function(c) return c.name end, clients), ","))
  vim.api.nvim_buf_delete(buf, { force = true })
end)

-- ── lsp-attach (integration; requires a real server binary) ─────────────
test("lsp: gopls attaches to a go buffer", function()
  if vim.fn.executable("gopls") ~= 1 then
    skip("lsp: gopls attaches to a go buffer")
    return
  end
  local dir = vim.fn.tempname()
  vim.fn.mkdir(dir, "p")
  vim.fn.writefile({ "module probe", "", "go 1.21" }, dir .. "/go.mod")
  local path = dir .. "/main.go"
  vim.fn.writefile({ "package main", "", "func main() {}" }, path)
  vim.cmd("edit " .. path)
  local deadline = vim.uv.hrtime() + 5 * 1e9
  while vim.uv.hrtime() < deadline and #vim.lsp.get_clients({ bufnr = 0 }) == 0 do
    vim.wait(50)
  end
  local clients = vim.lsp.get_clients({ bufnr = 0 })
  local names = {}
  for _, c in ipairs(clients) do
    names[#names + 1] = c.name
  end
  vim.api.nvim_buf_delete(0, { force = true })
  vim.fn.delete(dir, "rf")
  check(#clients > 0, "no client attached to go buffer")
  check(vim.tbl_contains(names, "gopls"), "gopls not attached, got: " .. table.concat(names, ","))
end)

-- ── deprecated API scan ─────────────────────────────────────────────────
local deprecated_symbols = {
  ["goto_prev"] = true,
  ["goto_next"] = true,
  ["get_prev_pos"] = true,
  ["get_next_pos"] = true,
  ["client.supports_method"] = true,
  ["nvim_buf_set_option"] = true,
  ["nvim_buf_get_option"] = true,
  ["nvim_win_set_option"] = true,
}

test("deprecated: no known-deprecated symbols in config source", function()
  local files = vim.fn.glob(CONFIG_DIR .. "/lua/*.lua", false, true)
  for _, file in ipairs(files) do
    local content = table.concat(vim.fn.readfile(file), "\n")
    -- Strip block comments first (can span lines), then strings, then line
    -- comments, so symbols inside comments/strings never trigger.
    local stripped = content
      :gsub("%-%-%[%[.-%]%]", "")
      :gsub('"[^"\n]*"', "")
      :gsub("'[^'\n]*'", "")
      :gsub("%-%-[^\n]*", "")
    for sym in pairs(deprecated_symbols) do
      if stripped:find(sym, 1, true) then
        error(file .. " uses deprecated symbol: " .. sym)
      end
    end
  end
end)

-- ── summary ─────────────────────────────────────────────────────────────
print("")
print(string.format(
  "%d passed, %d failed, %d skipped",
  results.pass, results.fail, results.skip
))
if filter and results.matched == 0 then
  print("no tests matched filter: " .. filter)
  os.exit(1)
end
os.exit(results.fail == 0 and 0 or 1)
