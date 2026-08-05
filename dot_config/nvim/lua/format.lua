-- No-plugin format-on-save. Prefers LSP formatting; falls back to a
-- per-filetype external formatter command when no LSP client is attached.
-- Formatters must be installed system-wide.

local formatters = {
  go = { "gofmt" },
  sh = { "shfmt" },
  bash = { "shfmt" },
  zsh = { "shfmt" },
  rust = { "rustfmt" },
  python = { "black" },
  lua = { "stylua" },
  javascript = { "prettierd", "prettier" },
  javascriptreact = { "prettierd", "prettier" },
  typescript = { "prettierd", "prettier" },
  typescriptreact = { "prettierd", "prettier" },
  json = { "prettierd", "prettier" },
  jsonc = { "prettierd", "prettier" },
  markdown = { "prettierd", "prettier" },
  yaml = { "yamlfmt" },
  yml = { "yamlfmt" },
}

local function pick_first_available(candidates)
  for _, name in ipairs(candidates) do
    if vim.fn.executable(name) == 1 then
      return name
    end
  end
  return nil
end

local function format_external(filetype, name)
  local ok = vim.api.nvim_buf_call(0, function()
    return vim.fn.system({ name, vim.fn.expand("%:p") }) == 0
  end)
  if not ok then
    vim.notify("Formatter failed: " .. name, vim.log.levels.WARN)
  end
end

local function format_buffer()
  local filetype = vim.bo.filetype
  if filetype == "" then
    return
  end

  -- Prefer LSP formatting when a client is attached.
  local clients = vim.lsp.get_clients({ bufnr = 0 })
  for _, client in ipairs(clients) do
    if client:supports_method("textDocument/formatting") then
      vim.lsp.buf.format({ bufnr = 0, async = false })
      return
    end
  end

  -- Fallback: external formatter for this filetype.
  local formatter = pick_first_available(formatters[filetype] or {})
  if formatter then
    format_external(filetype, formatter)
  end
end

local autocmd = vim.api.nvim_create_autocmd
autocmd("BufWritePre", {
  pattern = "*",
  callback = function()
    format_buffer()
  end,
})

return { format_buffer = format_buffer }
