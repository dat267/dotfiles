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
