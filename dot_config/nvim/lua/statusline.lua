-- Minimal built-in statusline: no plugins.
local modes = {
  ["n"] = "NORMAL",
  ["no"] = "N·O",
  ["v"] = "VISUAL",
  ["V"] = "V·LINE",
  ["\22"] = "V·BLOCK",
  ["i"] = "INSERT",
  ["R"] = "REPLACE",
  ["c"] = "COMMAND",
  ["t"] = "TERMINAL",
}

local function mode()
  local m = vim.api.nvim_get_mode().mode
  return modes[m] or m:upper()
end

local function lsp_status()
  local clients = vim.lsp.get_clients({ bufnr = 0 })
  if #clients == 0 then
    return ""
  end
  local names = vim.tbl_map(function(c)
    return c.name
  end, clients)
  return " " .. table.concat(names, ",")
end

local function diagnostic_count(severity)
  local n = #vim.diagnostic.get(0, { severity = severity })
  return n > 0 and n or ""
end

vim.opt.statusline = "%!v:lua.require'statusline'.build()"

local M = {}

function M.build()
  local bufname = vim.api.nvim_buf_get_name(0)
  local file = bufname ~= "" and vim.fn.fnamemodify(bufname, ":t") or "[No Name]"
  local modified = vim.bo.modified and " +" or ""

  return table.concat({
    "%#StatuslineAccent#" .. mode() .. "%*",
    " " .. file .. modified .. " ",
    "%#StatuslineLineNr#%{&ff} %{&fenc!=''?&fenc:&enc}%*",
    " " .. lsp_status(),
    " %#StatuslineDiagnosticError#" .. diagnostic_count(vim.diagnostic.severity.ERROR) .. "%*",
    " %#StatuslineDiagnosticWarn#" .. diagnostic_count(vim.diagnostic.severity.WARN) .. "%*",
    "%=%#StatuslineLineNr#%l:%c %P%*",
  })
end

return M
