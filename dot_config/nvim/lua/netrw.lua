-- netrw: built-in file explorer, minimal tweaks.
vim.g.netrw_banner = 0
vim.g.netrw_liststyle = 3
vim.g.netrw_browse_split = 4
vim.g.netrw_winsize = 25
vim.g.netrw_altv = 1
if vim.fn.exists("netrw_gitignore#Hide") == 1 then
  vim.g.netrw_list_hide = vim.call("netrw_gitignore#Hide") .. ",^\\.\\+\\%#"
end

-- <leader>e maps to :Explore in keymaps.lua
local map = vim.keymap.set
map("n", "<leader>e", "<cmd>Lexplore<cr>", { desc = "file explorer (netrw)" })
