vim.g.mapleader = " "
vim.g.maplocalleader = " "

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

vim.cmd.colorscheme("catppuccin")
