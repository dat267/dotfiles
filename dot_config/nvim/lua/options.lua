local opt = vim.opt

opt.number = true
opt.relativenumber = true
opt.scrolloff = 8
opt.inccommand = "split"

opt.tabstop = 4
opt.shiftwidth = 4
opt.softtabstop = 4
opt.expandtab = true
opt.smartindent = true

opt.list = true
opt.listchars = { tab = "» ", trail = "·", nbsp = "␣" }

opt.mouse = "a"
opt.termguicolors = true
opt.splitright = true
opt.splitbelow = true
opt.ignorecase = true
opt.smartcase = true
opt.hlsearch = true
opt.wrap = false
opt.signcolumn = "yes"
opt.updatetime = 250
opt.undofile = true
opt.swapfile = false
opt.clipboard = "unnamedplus"

local autocmd = vim.api.nvim_create_autocmd
autocmd("OptionSet", {
  pattern = "clipboard",
  callback = function()
    vim.opt.clipboard:append "unnamedplus"
  end,
})

if vim.env.SSH_TTY then
  vim.g.clipboard = {
    name = "OSC 52",
    copy = {
      ["+"] = require("vim.ui.clipboard.osc52").copy("+"),
      ["*"] = require("vim.ui.clipboard.osc52").copy("*"),
    },
    paste = {
      ["+"] = function()
        return vim.fn.split(vim.fn.getreg(), "\n")
      end,
      ["*"] = function()
        return vim.fn.split(vim.fn.getreg(), "\n")
      end,
    },
  }
end
