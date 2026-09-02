vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- Disable background DSR query (E1568 in terminals that don't respond)
vim.cmd("silent! set t_RB=")

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
