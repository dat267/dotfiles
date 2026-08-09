local M = {}

local snippets = {
  go = {
    { trig = "main",   body = "func main() {\n\t${1:}\n}\n",   desc = "main function" },
    { trig = "struct", body = "type ${1:Name} struct {\n\t${2}\n}\n", desc = "struct type" },
    { trig = "iface",  body = "type ${1:Name} interface {\n\t${2}\n}\n", desc = "interface type" },
  },
}

local items = {}
for ft, list in pairs(snippets) do
  items[ft] = {}
  for _, s in ipairs(list) do
    items[ft][s.trig] = {
      word = s.trig,
      abbr = s.trig,
      menu = "[snip]",
      user_data = vim.json.encode({ snip = s.body, trig = s.trig }),
    }
  end
end

local IDENT_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

function M.merge_trigger_chars(server_chars)
  local set = {}
  for _, c in ipairs(server_chars or {}) do
    set[c] = true
  end
  for c in IDENT_CHARS:gmatch(".") do
    set[c] = true
  end
  local out = {}
  for c in pairs(set) do
    out[#out + 1] = c
  end
  return out
end

function M.merge_items(matches, start_col)
  local ft_items = items[vim.bo.filetype]
  if not ft_items then
    return matches
  end
  local cleaned = {}
  for _, m in ipairs(matches) do
    if m.menu ~= "[snip]" then
      cleaned[#cleaned + 1] = m
    end
  end
  local line = vim.api.nvim_get_current_line()
  local cursor_col = vim.api.nvim_win_get_cursor(0)[2]
  local prefix = ""
  if start_col and start_col >= 1 and start_col <= cursor_col + 1 then
    prefix = line:sub(start_col, cursor_col + 1)
  end
  for trig, item in pairs(ft_items) do
    if trig:sub(1, #prefix) == prefix then
      cleaned[#cleaned + 1] = item
    end
  end
  return cleaned
end

function M.expand_completed(item)
  if not item or type(item.user_data) ~= "string" then
    return false
  end
  local ok, ud = pcall(vim.json.decode, item.user_data)
  if not ok or type(ud) ~= "table" or not ud.snip then
    return false
  end
  local row, col = unpack(vim.api.nvim_win_get_cursor(0))
  local word = item.word or ud.trig
  local start = col - #word
  if start < 0 then
    return false
  end
  vim.api.nvim_buf_set_text(0, row - 1, start, row - 1, col, {})
  vim.api.nvim_win_set_cursor(0, { row, start })
  vim.snippet.expand(ud.snip)
  return true
end

function M.setup()
  if M._setup then
    return
  end
  M._setup = true

  local orig = vim.fn.complete
  vim.fn.complete = function(start_col, matches)
    if type(matches) == "table" and items[vim.bo.filetype] then
      matches = M.merge_items(matches, start_col)
    end
    return orig(start_col, matches)
  end

  vim.api.nvim_create_autocmd("CompleteDone", {
    callback = function()
      M.expand_completed(vim.v.completed_item)
    end,
    desc = "expand custom snippets",
  })
end

return M
