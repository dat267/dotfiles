-- Neovim 0.12 has treesitter built in. Enable highlighting + folds for
-- supported filetypes. Parsers must be installed system-wide; if a parser
-- is missing, nvim falls back to regex highlighting automatically.
vim.treesitter.start = vim.treesitter.start

local autocmd = vim.api.nvim_create_autocmd

autocmd("FileType", {
  callback = function()
    local ok = pcall(vim.treesitter.start)
    if not ok then
      vim.opt.syntax = "on"
    end
  end,
})

-- Folds via treesitter where available
autocmd("FileType", {
  pattern = { "go", "python", "javascript", "typescript", "json", "yaml", "lua" },
  callback = function()
    vim.opt_local.foldmethod = "expr"
    vim.opt_local.foldexpr = "v:lua.vim.treesitter.foldexpr()"
    vim.opt_local.foldlevel = 99
  end,
})
