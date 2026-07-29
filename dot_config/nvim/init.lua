vim.g.loaded_node_provider = 0
vim.g.loaded_perl_provider = 0
vim.g.loaded_ruby_provider = 0

vim.opt.clipboard = "unnamedplus"
if vim.env.SSH_TTY then
  vim.g.clipboard = {
    name = "OSC 52",
    copy = {
      ["+"] = require("vim.ui.clipboard.osc52").copy("+"),
      ["*"] = require("vim.ui.clipboard.osc52").copy("*"),
    },
    paste = {
      ["+"] = function() return vim.fn.split(vim.fn.getreg(""), "\n") end,
      ["*"] = function() return vim.fn.split(vim.fn.getreg(""), "\n") end,
    },
  }
end

vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.expandtab = true
vim.opt.smartindent = true
vim.opt.undofile = true
vim.opt.termguicolors = true
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.updatetime = 300
vim.opt.completeopt = { "menu", "menuone", "noselect" }
vim.opt.scrolloff = 8
vim.opt.inccommand = "split"
vim.opt.splitright = true
vim.opt.splitbelow = true
vim.g.mapleader = " "

vim.api.nvim_create_autocmd("FileType", {
  pattern = "go",
  callback = function()
    vim.bo.tabstop = 4
    vim.bo.shiftwidth = 4
    vim.bo.softtabstop = 4
    vim.bo.expandtab = false
  end,
})

vim.keymap.set("n", "<leader>w", "<cmd>w<cr>", { desc = "Save" })
vim.keymap.set("n", "<leader>q", "<cmd>q<cr>", { desc = "Quit" })
vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<cr>", { desc = "Clear search" })
vim.keymap.set("n", "<C-h>", "<C-w>h", { desc = "Window left" })
vim.keymap.set("n", "<C-j>", "<C-w>j", { desc = "Window down" })
vim.keymap.set("n", "<C-k>", "<C-w>k", { desc = "Window up" })
vim.keymap.set("n", "<C-l>", "<C-w>l", { desc = "Window right" })
vim.keymap.set("n", "n", "nzzzv", { desc = "Next search" })
vim.keymap.set("n", "N", "Nzzzv", { desc = "Prev search" })
vim.keymap.set("n", "[d", function() vim.diagnostic.jump({ count = -1 }) end, { desc = "Prev diagnostic" })
vim.keymap.set("n", "]d", function() vim.diagnostic.jump({ count = 1 }) end, { desc = "Next diagnostic" })
vim.keymap.set("i", "<CR>", function()
  if vim.fn.pumvisible() == 1 then
    return vim.fn.complete_info({ "selected" }).selected ~= -1 and "<C-y>" or "<C-e>"
  end
  return "<CR>"
end, { expr = true })


if vim.fn.has("win32") == 1 or vim.fn.has("wsl") == 1 then
  local handle = io.popen("reg query HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v AppsUseLightTheme 2>nul")
  if handle then
    local result = handle:read("*a")
    handle:close()
    if result:match("0x1") then
      vim.o.background = "light"
    elseif result:match("0x0") then
      vim.o.background = "dark"
    end
  end
else
  local colorfgbg = os.getenv("COLORFGBG")
  if colorfgbg then
    local bg_val = colorfgbg:match(".*;(%d+)$")
    if bg_val and tonumber(bg_val) > 0 then
      vim.o.background = "light"
    end
  end
end

require("theme").setup(vim.o.background)

vim.diagnostic.config({
  virtual_text = false,
  virtual_lines = false,
  signs = true,
  underline = true,
  update_in_insert = false,
  severity_sort = true,
  float = {
    source = true,
    prefix = function(diag)
      return ({ "E", "W", "I", "H" })[diag.severity] or "?"
    end,
  },
})

vim.api.nvim_create_autocmd("CursorHold", {
  callback = function()
    vim.diagnostic.open_float({ scope = "cursor" })
  end,
})

vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(event)
    local client = vim.lsp.get_client_by_id(event.data.client_id)
    if not client then return end
    local buf = event.buf
    local opts = { buffer = buf }

    local maps = {
      ["textDocument/definition"] = { "n", "gd", vim.lsp.buf.definition },
      ["textDocument/references"] = { "n", "gr", vim.lsp.buf.references },
      ["textDocument/hover"] = { "n", "K", vim.lsp.buf.hover },
      ["textDocument/rename"] = { "n", "<leader>rn", vim.lsp.buf.rename },
      ["textDocument/codeAction"] = { { "n", "v" }, "<leader>ca", vim.lsp.buf.code_action },
      ["textDocument/signatureHelp"] = { "i", "<C-k>", vim.lsp.buf.signature_help },
    }
    for method, m in pairs(maps) do
      if client:supports_method(method) then
        vim.keymap.set(m[1], m[2], m[3], opts)
      end
    end

    if client:supports_method("textDocument/completion") then
      vim.bo[buf].omnifunc = "v:lua.vim.lsp.omnifunc"
    end

    if client:supports_method("textDocument/documentHighlight") then
      local group = vim.api.nvim_create_augroup("LspHighlight." .. buf, { clear = false })
      vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" },
        { buffer = buf, group = group, callback = vim.lsp.buf.document_highlight })
      vim.api.nvim_create_autocmd({ "CursorMoved", "CursorMovedI" },
        { buffer = buf, group = group, callback = vim.lsp.buf.clear_references })
    end

    if client:supports_method("textDocument/inlayHint") then
      vim.lsp.inlay_hint.enable(true, { bufnr = buf })
    end

    if vim.bo[buf].filetype ~= "go" and client:supports_method("textDocument/formatting") then
      vim.api.nvim_create_autocmd("BufWritePre", {
        buffer = buf,
        callback = function()
          vim.lsp.buf.format({ bufnr = buf, id = client.id })
        end,
      })
    end
  end,
})

vim.api.nvim_create_autocmd("TextChangedI", {
  group = vim.api.nvim_create_augroup("LspAutoComplete", { clear = true }),
  callback = function()
    if vim.fn.pumvisible() > 0 then return end
    local col = vim.fn.col(".")
    local line = vim.fn.getline(".")
    if col < 2 then return end
    if line:sub(col - 1, col - 1):match("[%w_]") then
      if vim.lsp.completion then
        vim.lsp.completion.trigger()
      elseif vim.bo.omnifunc ~= "" then
        local keys = vim.api.nvim_replace_termcodes("<C-x><C-o>", true, false, true)
        vim.api.nvim_feedkeys(keys, "i", false)
      end
    end
  end,
})

local lsp_modules = {
  go_lsp = "gopls",
  lua_lsp = "lua-language-server",
  js_lsp = "typescript-language-server",
  py_lsp = "pyright",
  ps1_lsp = "pwsh",
  md_lsp = "marksman",
  rs_lsp = "rust-analyzer",
  sh_lsp = "bash-language-server",
}
for module, binary in pairs(lsp_modules) do
  if vim.fn.executable(binary) == 1 then
    if module ~= "ps1_lsp" or not vim.env.TERMUX_VERSION then
      local ok, err = pcall(require, module)
      if not ok then
        vim.schedule(function()
          vim.notify("Error loading " .. module .. ": " .. tostring(err), vim.log.levels.ERROR)
        end)
      end
    end
  end
end
