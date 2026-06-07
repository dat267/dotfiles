vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 2
vim.opt.shiftwidth = 2
vim.opt.expandtab = true
vim.opt.smartindent = true
vim.opt.undofile = true
vim.opt.clipboard = "unnamedplus"
vim.opt.termguicolors = true
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.updatetime = 300
vim.opt.statusline = " %f %m %r %= %y  %l:%c "
vim.opt.completeopt = { "menu", "menuone", "noselect" }
vim.opt.shortmess:append("c")
vim.opt.whichwrap:append("<,>,[,]")
vim.g.mapleader = " "

vim.keymap.set("n", "<leader>w", "<cmd>w<cr>", { desc = "Save file" })
vim.keymap.set("n", "<leader>q", "<cmd>q<cr>", { desc = "Quit" })
vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<cr>", { desc = "Clear highlight" })
vim.keymap.set("n", "[d", function() vim.diagnostic.jump({ count = -1 }) end)
vim.keymap.set("n", "]d", function() vim.diagnostic.jump({ count = 1 }) end)
vim.keymap.set("i", "<Tab>", function() return vim.fn.pumvisible() == 1 and "<C-n>" or "<Tab>" end, { expr = true })
vim.keymap.set("i", "<S-Tab>", function() return vim.fn.pumvisible() == 1 and "<C-p>" or "<S-Tab>" end, { expr = true })

local function apply_transparency()
  local hl_groups = {
    "Normal", "NormalNC", "SignColumn", "LineNr", "CursorLineNr",
    "EndOfBuffer", "NonText", "Folded", "StatusLine", "StatusLineNC",
    "VertSplit", "WinSeparator", "NormalFloat", "FloatBorder", "Pmenu"
  }
  for _, group in ipairs(hl_groups) do
    vim.api.nvim_set_hl(0, group, { bg = "none", ctermbg = "none" })
  end
end
apply_transparency()

vim.api.nvim_create_autocmd("ColorScheme", { callback = apply_transparency })

local builtin_theme = vim.o.background == "light" and "quiet" or "habamax"
pcall(vim.cmd.colorscheme, builtin_theme)

vim.api.nvim_create_autocmd("OptionSet", {
  pattern = "background",
  callback = function()
    local theme = vim.o.background == "light" and "quiet" or "habamax"
    pcall(vim.cmd.colorscheme, theme)
  end,
})

vim.diagnostic.config({
  virtual_text = false,
  virtual_lines = { current_line = true },
  signs = true,
  underline = true,
  update_in_insert = false,
  severity_sort = true,
})

vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(event)
    local client = vim.lsp.get_client_by_id(event.data.client_id)
    if not client then return end
    local opts = { buffer = event.buf }

    local methods = {
      ["textDocument/definition"] = { "n", "gd", vim.lsp.buf.definition },
      ["textDocument/references"] = { "n", "gr", vim.lsp.buf.references },
      ["textDocument/hover"] = { "n", "K", vim.lsp.buf.hover },
      ["textDocument/rename"] = { "n", "<leader>rn", vim.lsp.buf.rename },
      ["textDocument/codeAction"] = { { "n", "v" }, "<leader>ca", vim.lsp.buf.code_action },
      ["textDocument/signatureHelp"] = { "i", "<C-k>", vim.lsp.buf.signature_help },
    }
    for method, map in pairs(methods) do
      if client:supports_method(method) then vim.keymap.set(map[1], map[2], map[3], opts) end
    end

    if client:supports_method("textDocument/completion") then
      local provider = client.server_capabilities.completionProvider or {}
      provider.triggerCharacters = provider.triggerCharacters or {}
      local chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
      for i = 1, #chars do table.insert(provider.triggerCharacters, chars:sub(i, i)) end
      vim.lsp.completion.enable(true, client.id, event.buf, { autotrigger = true })
    end

    if client:supports_method("textDocument/documentHighlight") then
      local group = vim.api.nvim_create_augroup("LspDocumentHighlight", { clear = false })
      vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" },
        { buffer = event.buf, group = group, callback = vim.lsp.buf.document_highlight })
      vim.api.nvim_create_autocmd({ "CursorMoved", "CursorMovedI" },
        { buffer = event.buf, group = group, callback = vim.lsp.buf.clear_references })
    end

    if client:supports_method("textDocument/inlayHint") then
      vim.lsp.inlay_hint.enable(true, { bufnr = event.buf })
    end
    if client:supports_method("textDocument/formatting") then
      local format_group = vim.api.nvim_create_augroup("LspFormatting", { clear = false })
      vim.api.nvim_create_autocmd("BufWritePre", {
        buffer = event.buf,
        group = format_group,
        callback = function()
          vim.lsp.buf.format({ bufnr = event.buf, id = client.id })
        end,
      })
    end
  end,
})

local pair_map = { ["("] = ")", ["["] = "]", ["{"] = "}", ['"'] = '"', ["'"] = "'", ["`"] = "`" }
for open, close in pairs(pair_map) do
  if open == close then
    vim.keymap.set("i", open, function()
      local col = vim.api.nvim_win_get_cursor(0)[2]
      local line = vim.api.nvim_get_current_line()
      return line:sub(col + 1, col + 1) == close and "<Right>" or open .. close .. "<Left>"
    end, { expr = true })
  else
    vim.keymap.set("i", open, open .. close .. "<Left>")
    vim.keymap.set("i", close, function()
      local col = vim.api.nvim_win_get_cursor(0)[2]
      local line = vim.api.nvim_get_current_line()
      return line:sub(col + 1, col + 1) == close and "<Right>" or close
    end, { expr = true })
  end
end

vim.keymap.set("i", "<BS>", function()
  local col = vim.api.nvim_win_get_cursor(0)[2]
  local line = vim.api.nvim_get_current_line()
  return pair_map[line:sub(col, col)] == line:sub(col + 1, col + 1) and "<BS><Del>" or "<BS>"
end, { expr = true })

vim.keymap.set("i", "<CR>", function()
  local col = vim.api.nvim_win_get_cursor(0)[2]
  local line = vim.api.nvim_get_current_line()
  return (line:sub(col, col) == "{" and line:sub(col + 1, col + 1) == "}") and "<CR><Esc>O" or "<CR>"
end, { expr = true })

vim.api.nvim_create_autocmd("TextChangedI", {
  callback = function()
    if vim.fn.pumvisible() ~= 0 or vim.bo.omnifunc == "" then return end
    local col = vim.api.nvim_win_get_cursor(0)[2]
    local line = vim.api.nvim_get_current_line()
    local char = line:sub(col, col)
    if char:match("[%w_%.%:]") then
      vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<C-x><C-o>", true, true, true), "n", false)
    end
  end,
})

local formatters = {
  py = { bin = "black", cmd = "black -q -" },
  md = { bin = "prettier", cmd = "prettier --parser markdown" }
}

vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = { "*.py", "*.md" },
  callback = function()
    local ext = vim.fn.expand("<afile>:e")
    local fmt = formatters[ext]
    if fmt and vim.fn.executable(fmt.bin) == 1 then
      local view = vim.fn.winsaveview()
      vim.cmd("%!" .. fmt.cmd)
      if vim.v.shell_error ~= 0 then vim.cmd("undo") end
      vim.fn.winrestview(view)
    end
  end,
})

local lsp_modules = {
  lua_lsp = "lua-language-server",
  go_lsp = "gopls",
  js_lsp = "typescript-language-server",
  py_lsp = "pyright",
  ps1_lsp = "pwsh",
  md_lsp = "marksman",
  rs_lsp = "rust-analyzer",
}

for module, binary in pairs(lsp_modules) do
  if vim.fn.executable(binary) == 1 then
    if module ~= "powershell_lsp" or not vim.env.TERMUX_VERSION then
      pcall(require, module)
    end
  end
end

