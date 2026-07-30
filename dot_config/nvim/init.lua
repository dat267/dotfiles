vim.g.loaded_node_provider = 0
vim.g.loaded_perl_provider = 0
vim.g.loaded_ruby_provider = 0
vim.g.loaded_python3_provider = 0

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

vim.api.nvim_create_autocmd("VimLeavePre", {
  group = vim.api.nvim_create_augroup("SaveMessagesLogOnExit", { clear = true }),
  callback = function()
    local log_dir = vim.fn.stdpath("config")
    if vim.fn.isdirectory(log_dir) == 0 then
      vim.fn.mkdir(log_dir, "p")
    end
    local log_file = log_dir .. "/messages.log"
    local msgs = vim.fn.execute("messages")
    if msgs and msgs:match("%S") then
      local timestamp = os.date("%Y-%m-%d %H:%M:%S")
      local header = string.format("--- Session exited at %s ---\n", timestamp)
      local f = io.open(log_file, "a")
      if f then
        f:write(header .. msgs .. "\n\n")
        f:close()
      end
    end
  end,
})
