local autocmd = vim.api.nvim_create_autocmd

-- Go: tabs, no expandtab
autocmd("FileType", {
  pattern = "go",
  callback = function()
    vim.bo.tabstop = 4
    vim.bo.shiftwidth = 4
    vim.bo.softtabstop = 4
    vim.bo.expandtab = false
  end,
})

-- YAML: 2-space indent
autocmd("FileType", {
  pattern = { "yaml", "yml" },
  callback = function()
    vim.bo.tabstop = 2
    vim.bo.shiftwidth = 2
    vim.bo.softtabstop = 2
  end,
})

-- Reload file if changed outside (no prompt)
autocmd("FocusGained", {
  pattern = "*",
  callback = function()
    if vim.bo.modified then
      return
    end
    vim.cmd "checktime"
  end,
})

-- Trim trailing whitespace on save
autocmd("BufWritePre", {
  pattern = "*",
  callback = function()
    local save = vim.fn.winsaveview()
    vim.cmd "%s/\\s\\+$//e"
    vim.fn.winrestview(save)
  end,
})

-- Quickfix / location list: <CR> jumps and closes, q / <Esc> close it.
autocmd("FileType", {
  pattern = { "qf" },
  callback = function()
    local map = vim.keymap.set
    map("n", "q", "<cmd>lclose<cr>", { buffer = true, desc = "close location list" })
    map("n", "<Esc>", "<cmd>lclose<cr>", { buffer = true, desc = "close location list" })
    map("n", "<CR>", "<CR><cmd>lclose<cr>", { buffer = true, desc = "jump and close" })
  end,
})

-- Restore last edit position when reopening a file.
autocmd("BufReadPost", {
  pattern = "*",
  callback = function()
    local mark = vim.api.nvim_buf_get_mark(0, '"')
    local line_count = vim.api.nvim_buf_line_count(0)
    if mark[1] > 0 and mark[1] <= line_count then
      vim.api.nvim_win_set_cursor(0, { mark[1], mark[2] })
    end
  end,
})

-- Highlight the text just yanked (flash the region briefly).
autocmd("TextYankPost", {
  pattern = "*",
  callback = function()
    if vim.v.event.operator == "y" then
      vim.highlight.on_yank({ higroup = "IncSearch", timeout = 150 })
    end
  end,
})
