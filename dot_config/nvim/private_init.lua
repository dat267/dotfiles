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
vim.opt.statusline = " %f %m %r %= %y  %l:%c "
vim.g.mapleader = " "
vim.keymap.set("n", "<leader>w", "<cmd>w<cr>", { desc = "Save file" })
vim.keymap.set("n", "<leader>q", "<cmd>q<cr>", { desc = "Quit" })
vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<cr>", { desc = "Clear highlight" })
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
vim.api.nvim_create_autocmd("ColorScheme", {
	callback = apply_transparency
})
local builtin_theme = vim.o.background == "light" and "quiet" or "habamax"
pcall(vim.cmd.colorscheme, builtin_theme)
vim.api.nvim_create_autocmd("OptionSet", {
	pattern = "background",
	callback = function()
		local theme = vim.o.background == "light" and "quiet" or "habamax"
		pcall(vim.cmd.colorscheme, theme)
	end,
})
pcall(require, "personal")
-- Extensibility:
-- 1. Add custom lua config: create ~/.config/nvim/lua/personal.lua
-- 2. Add local plugins: place in ~/.config/nvim/pack/plugins/start/
require("lua_lsp")
require("go_lsp")
require("js_lsp")
require("python_lsp")

