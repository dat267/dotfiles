local map = vim.keymap.set

-- Leader basics
map("n", "<leader>w", "<cmd>w<cr>", { desc = "save file" })
map("n", "<leader>q", "<cmd>q<cr>", { desc = "quit window" })
map("n", "<leader>Q", "<cmd>qa<cr>", { desc = "quit all" })

-- Keep search result centered
map("n", "n", "nzzzv", { desc = "next search result" })
map("n", "N", "Nzzzv", { desc = "prev search result" })

-- Window management
map("n", "<leader>sv", "<cmd>vsplit<cr>", { desc = "vertical split" })
map("n", "<leader>sh", "<cmd>split<cr>", { desc = "horizontal split" })
map("n", "<C-h>", "<C-w>h", { desc = "focus left" })
map("n", "<C-j>", "<C-w>j", { desc = "focus down" })
map("n", "<C-k>", "<C-w>k", { desc = "focus up" })
map("n", "<C-l>", "<C-w>l", { desc = "focus right" })

-- Buffer navigation
map("n", "<leader>bn", "<cmd>bn<cr>", { desc = "next buffer" })
map("n", "<leader>bp", "<cmd>bp<cr>", { desc = "prev buffer" })
map("n", "<leader>bd", "<cmd>bd<cr>", { desc = "delete buffer" })

-- Find files (built-in)
map("n", "<leader>ff", "<cmd>find **/*<cr>", { desc = "find files" })
map("n", "<leader>fg", "<cmd>vimgrep // **/*<left><left><left><left><left><left>", { desc = "live grep" })

-- Terminal
map("n", "<leader>t", "<cmd>terminal<cr>", { desc = "open terminal" })
map("t", "<Esc>", "<C-\\><C-n>", { desc = "exit terminal" })

-- Better paste
map("v", "p", '"_dP', { desc = "paste without overwriting register" })

-- Move lines
map("v", "<A-j>", ":m '>+1<CR>gv=gv", { desc = "move line down" })
map("v", "<A-k>", ":m '<-2<CR>gv=gv", { desc = "move line up" })
