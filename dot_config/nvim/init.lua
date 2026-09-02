vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- Disable background DSR query (E1568)
vim.api.nvim_create_autocmd("UIEnter", {
  callback = function()
    vim.cmd("set t_RB=")
  end,
})

require "options"
require "keymaps"
require "autocmds"
require "treesitter"
require "netrw"
require "statusline"
require "brackets"
require "comments"
require "format"
require "lsp"
