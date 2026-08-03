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

-- Quickfix / location list navigation
map("n", "[q", "<cmd>cprev<cr>", { desc = "previous quickfix item" })
map("n", "]q", "<cmd>cnext<cr>", { desc = "next quickfix item" })
map("n", "[Q", "<cmd>cfirst<cr>", { desc = "first quickfix item" })
map("n", "]Q", "<cmd>clast<cr>", { desc = "last quickfix item" })
map("n", "[l", "<cmd>lprev<cr>", { desc = "previous location item" })
map("n", "]l", "<cmd>lnext<cr>", { desc = "next location item" })
map("n", "<leader>cq", "<cmd>copen<cr>", { desc = "open quickfix" })
map("n", "<leader>cl", "<cmd>lopen<cr>", { desc = "open location list" })
map("n", "<leader>cx", "<cmd>cclose<cr>", { desc = "close quickfix" })

-- Terminal
map("n", "<leader>t", "<cmd>terminal<cr>", { desc = "open terminal" })
map("t", "<Esc>", "<C-\\><C-n>", { desc = "exit terminal" })

-- Better paste
map("v", "p", '"_dP', { desc = "paste without overwriting register" })

-- Move lines
map("v", "<A-j>", ":m '>+1<CR>gv=gv", { desc = "move line down" })
map("v", "<A-k>", ":m '<-2<CR>gv=gv", { desc = "move line up" })
