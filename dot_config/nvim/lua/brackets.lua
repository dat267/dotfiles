-- No-plugin auto brackets using InsertCharPre for full context awareness.
-- Features: auto-pair, smart skip over existing closer, pair-aware backspace,
-- no pairing inside strings/comments, visual-mode selection wrapping.

local M = {}

local bracket_pairs = {
  ["("] = ")",
  ["["] = "]",
  ["{"] = "}",
  ['"'] = '"',
  ["'"] = "'",
  ["`"] = "`",
}

-- True when the cursor sits in a string/comment/character region (so quotes
-- and brackets typed there don't get auto-paired).
local function in_special_region()
  local row, col = vim.fn.line("."), vim.fn.col(".")
  local name = ""
  local ok = pcall(function()
    name = vim.fn.synIDattr(vim.fn.synID(row, col, 1), "name")
  end)
  if not ok then
    return false
  end
  return name:find("String") ~= nil
    or name:find("Comment") ~= nil
    or name:find("Character") ~= nil
end

-- Char immediately after the cursor on the current line, or "".
local function char_after_cursor()
  local line = vim.api.nvim_get_current_line()
  local col = vim.fn.col(".") - 1
  return line:sub(col + 1, col + 1)
end

-- Char immediately before the cursor on the current line, or "".
local function char_before_cursor()
  local line = vim.api.nvim_get_current_line()
  local col = vim.fn.col(".") - 1
  return line:sub(col, col)
end

local autocmd = vim.api.nvim_create_autocmd
autocmd("InsertCharPre", {
  callback = function()
    local char = vim.v.char
    local closer = bracket_pairs[char]

    -- Quote/backtick: never auto-pair inside strings/comments/characters.
    if char == '"' or char == "'" or char == "`" then
      if in_special_region() then
        return
      end
    end

    local next_char = char_after_cursor()

    -- Smart skip: typing a closing bracket that already follows the cursor
    -- moves past it instead of inserting a duplicate.
    if not closer and next_char == char then
      vim.v.char = ""
      vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Right>", true, false, true), "in", false)
      return
    end

    if not closer then
      return
    end

    -- Smart skip for open bracket: if the closer already follows, skip it.
    if next_char == closer then
      vim.v.char = ""
      vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Right>", true, false, true), "in", false)
      return
    end

    -- Auto-pair: insert opening char (v:char) then closing char, cursor between.
    local keys = vim.api.nvim_replace_termcodes(closer .. "<Left>", true, false, true)
    vim.api.nvim_feedkeys(keys, "in", false)
  end,
})

-- Pair-aware backspace: <BS> on an empty pair removes both chars.
vim.keymap.set("i", "<BS>", function()
  local before = char_before_cursor()
  local after = char_after_cursor()
  local closer = bracket_pairs[before]
  local keys
  if closer and after == closer then
    keys = "<BS><Del>"
  else
    keys = "<BS>"
  end
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(keys, true, false, true), "in", false)
end, { desc = "smart backspace" })

-- <Tab> jumps past a closing bracket (or inserts a tab if not at one).
vim.keymap.set("i", "<Tab>", function()
  local after = char_after_cursor()
  if vim.tbl_contains(vim.tbl_values(bracket_pairs), after) then
    vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Right>", true, false, true), "in", false)
    return ""
  end
  return "<Tab>"
end, { expr = true, desc = "jump out of bracket" })

-- Visual mode: wrap the selection with a bracket pair.
for open, close in pairs(bracket_pairs) do
  vim.keymap.set("v", open, function()
    return open .. vim.fn.getreg("v") .. close
  end, { expr = true, desc = "wrap selection in " .. open .. close })
end
return M
