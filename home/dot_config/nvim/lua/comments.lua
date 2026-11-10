-- No-plugin comment toggle via vim.operatorfunc.
-- `gc{motion}` toggles comments over a motion, `gcc` toggles the current
-- line, `gc` in visual mode toggles the selection.

local line_comments = {
  go = "//",
  c = "//",
  cpp = "//",
  rust = "//",
  javascript = "//",
  javascriptreact = "//",
  typescript = "//",
  typescriptreact = "//",
  json = "//",
  jsonc = "//",
  lua = "--",
  sh = "#",
  bash = "#",
  zsh = "#",
  python = "#",
  yaml = "#",
  yml = "#",
  conf = "#",
  toml = "#",
  ["dockerfile"] = "#",
  vim = '"',
  ["vimwiki"] = "%",
}

local block_comments = {
  html = { "<!--", "-->" },
  css = { "/*", "*/" },
  scss = { "/*", "*/" },
  less = { "/*", "*/" },
  sql = { "/*", "*/" },
}

local function comment_str()
  local ft = vim.bo.filetype
  if line_comments[ft] then
    return line_comments[ft] .. " "
  end
  local block = block_comments[ft]
  if block then
    return { block[1], block[2] }
  end
  return nil
end

local function toggle_line(line, marker, is_block)
  local lead = line:match("^%s*") or ""
  local content = line:sub(#lead + 1)
  if is_block then
    local open, close = marker[1], marker[2]
    if content:match("^" .. vim.pesc(open) .. ".*" .. vim.pesc(close) .. "$") then
      return lead .. content:sub(#open + 1, -#close - 1):gsub("^%s+", ""):gsub("%s+$", "")
    end
    return lead .. open .. " " .. content .. " " .. close
  end
  if content:sub(1, #marker) == marker then
    return lead .. content:sub(#marker + 1):gsub("^%s+", "")
  end
  return lead .. marker .. content
end

local function toggle_range(first, last)
  local marker = comment_str()
  if not marker then
    return
  end
  local is_block = type(marker) == "table"
  local lines = vim.api.nvim_buf_get_lines(0, first - 1, last, false)
  for i, line in ipairs(lines) do
    lines[i] = toggle_line(line, marker, is_block)
  end
  vim.api.nvim_buf_set_lines(0, first - 1, last, false, lines)
end

local function operator_callback()
  local mode = vim.v.operator
  if mode == "line" then
    local first = vim.fn.line("'[" )
    local last = vim.fn.line("']")
    toggle_range(first, last)
  elseif mode == "char" then
    local first = vim.fn.line("'[")
    local last = vim.fn.line("']")
    toggle_range(first, last)
  end
end

vim.keymap.set("n", "gc", function()
  vim.o.operatorfunc = "v:lua.require'comments'.toggle"
  return "g@"
end, { expr = true, desc = "comment toggle operator" })

vim.keymap.set("n", "gcc", function()
  local line = vim.fn.line(".")
  toggle_range(line, line)
end, { desc = "comment toggle line" })

vim.keymap.set("v", "gc", function()
  local first = vim.fn.line("'<")
  local last = vim.fn.line("'>")
  toggle_range(first, last)
end, { desc = "comment toggle selection" })

-- Exposed for operatorfunc + headless testing
local M = {}
function M.toggle()
  operator_callback()
end
function M.toggle_test(first, last)
  toggle_range(first, last)
end
return M
