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

-- Optional colorscheme: this repo ships no plugins, so only apply
-- catppuccin if a runtime copy is actually installed (e.g. distro package).
pcall(vim.cmd, "colorscheme catppuccin")
