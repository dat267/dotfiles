-- "pi": the tier of pi's `system` theme used when a terminal reports nothing
-- (Termux does not answer OSC 10/11, and nvim cannot read OSC replies anyway).
-- ANSI indices 0-15 are rendered by the terminal with its own theme, so every
-- color adapts to light/dark and palette changes by itself. Neutral tokens use
-- the terminal's default foreground (pi draws these faint with SGR 2, which
-- nvim cannot emit); panels get no background. Slots follow TOKEN_FAMILIES and
-- TOKEN_SLOTS in pi's packages/coding-agent/src/modes/interactive/theme/system-theme.ts:
--   1 red errors/removals - 2 green strings/success - 3 yellow functions,
--   headings, search - 4 blue keywords/links - 5 violet types/numbers,
--   accents - 6 calamine variables.
--
-- Groups with a built-in background are cleared explicitly: unset groups
-- otherwise fall back to nvim's own default scheme, which forces colors again.
--
-- termguicolors must stay off: nvim enables it on truecolor terminals, and
-- with it on, groups that only carry cterm attributes (everything here) render
-- uncolored. With it off, nvim emits the ANSI indices above and the terminal
-- maps them to its own palette.
local opt = vim.opt
opt.termguicolors = false

local g = vim.g
local hl = vim.api.nvim_set_hl

g.colors_name = "pi"

-- Terminal default foreground/background, no panels (pi: neutral / "").
local plain = { "Normal", "Comment", "Operator", "Delimiter", "Conceal", "MsgArea", "LineNrAbove", "LineNrBelow" }
-- Bright black (pi uses SGR 2 faint for these; color 8 is the closest nvim can do).
local faint = { "LineNr", "NonText", "EndOfBuffer", "SpecialKey", "Whitespace", "FoldColumn", "StatusLineNC", "TabLine" }
local bgFree = { "CursorLine", "CursorColumn", "NormalFloat", "FloatBorder", "Pmenu", "PmenuSbar", "PmenuThumb", "SignColumn", "Folded", "TabLineFill", "StatusLineTerm" }

for _, name in ipairs(plain) do
  hl(0, name, {})
end
for _, name in ipairs(faint) do
  hl(0, name, { ctermfg = 8 })
end
for _, name in ipairs(bgFree) do
  hl(0, name, {})
end

-- Syntax (legacy groups; treesitter @ groups below).
hl(0, "Constant", { ctermfg = 5 })
hl(0, "Number", { ctermfg = 5 })
hl(0, "Boolean", { ctermfg = 5 })
hl(0, "Float", { ctermfg = 5 })
hl(0, "String", { ctermfg = 2 })
hl(0, "Character", { ctermfg = 2 })
hl(0, "SpecialChar", { ctermfg = 2 })
hl(0, "Identifier", { ctermfg = 6 })
hl(0, "Function", { ctermfg = 3 })
hl(0, "Statement", { ctermfg = 4 })
hl(0, "Keyword", { ctermfg = 4 })
hl(0, "Conditional", { ctermfg = 4 })
hl(0, "Repeat", { ctermfg = 4 })
hl(0, "Label", { ctermfg = 4 })
hl(0, "PreProc", { ctermfg = 5 })
hl(0, "Macro", { ctermfg = 5 })
hl(0, "Include", { ctermfg = 5 })
hl(0, "Define", { ctermfg = 5 })
hl(0, "Type", { ctermfg = 5 })
hl(0, "StorageClass", { ctermfg = 5 })
hl(0, "Structure", { ctermfg = 5 })
hl(0, "Typedef", { ctermfg = 5 })
hl(0, "Special", { ctermfg = 5 })
hl(0, "Tag", { ctermfg = 4 })
hl(0, "Underlined", { ctermfg = 4 })
hl(0, "Ignore", {})
hl(0, "Error", { ctermfg = 1 })
hl(0, "ErrorMsg", { ctermfg = 1 })
hl(0, "Exception", { ctermfg = 1 })
hl(0, "Todo", { ctermfg = 3, cterm = { bold = true } })
hl(0, "WarningMsg", { ctermfg = 3 })
hl(0, "MoreMsg", { ctermfg = 2 })
hl(0, "ModeMsg", { ctermfg = 2 })
hl(0, "Question", { ctermfg = 2 })
hl(0, "Title", { cterm = { bold = true } })
hl(0, "Directory", { ctermfg = 4 })

-- UI. Reverse (fg/bg swap) renders with the terminal's own colors, like pi's
-- terminal-rendered selection.
hl(0, "Visual", { cterm = { reverse = true } })
hl(0, "VisualNOS", { cterm = { reverse = true } })
-- Footer: no bar color, text sits on the terminal's own background (pi's tier-3
-- panels have no background either); mode emphasis comes from bold in the
-- statusline content itself.
hl(0, "StatusLine", { cterm = { bold = true } })
hl(0, "WildMenu", { cterm = { reverse = true } })
hl(0, "PmenuSel", { cterm = { reverse = true } })
hl(0, "PmenuKind", { ctermfg = 8 })
hl(0, "PmenuExtra", { ctermfg = 8 })
hl(0, "PmenuMatch", { ctermfg = 4 })
hl(0, "Cursor", { cterm = { reverse = true } })
hl(0, "TermCursor", { cterm = { reverse = true } })
hl(0, "CursorIM", { cterm = { reverse = true } })
hl(0, "CursorLineNr", { cterm = { bold = true } })
hl(0, "ColorColumn", { cterm = { reverse = true } })
hl(0, "WinSeparator", { ctermfg = 8 })
hl(0, "VertSplit", { ctermfg = 8 })
hl(0, "QuickFixLine", { cterm = { bold = true } })
hl(0, "TabLineSel", { cterm = { bold = true } })
hl(0, "SpellBad", { ctermfg = 1, cterm = { underline = true } })
hl(0, "SpellCap", { ctermfg = 3, cterm = { underline = true } })
hl(0, "SpellRare", { ctermfg = 3, cterm = { underline = true } })
hl(0, "SpellLocal", { ctermfg = 2, cterm = { underline = true } })
hl(0, "MatchParen", { ctermfg = 5, cterm = { bold = true } })

-- Search: orange slot 3 background, dark readable text (searchMatchText).
hl(0, "Search", { ctermfg = 0, ctermbg = 3 })
hl(0, "IncSearch", { cterm = { reverse = true } })
hl(0, "CurSearch", { cterm = { reverse = true, bold = true }, bold = true })
hl(0, "Substitute", { cterm = { reverse = true } })

-- Diff: foreground only, no panel backgrounds (toolDiffAdded/Removed/Context).
hl(0, "DiffAdd", { ctermfg = 2 })
hl(0, "Added", { ctermfg = 2 })
hl(0, "DiffDelete", { ctermfg = 1 })
hl(0, "Removed", { ctermfg = 1 })
hl(0, "DiffChange", { ctermfg = 3 })
hl(0, "Changed", { ctermfg = 3 })
hl(0, "DiffText", { ctermfg = 3, cterm = { bold = true } })

-- Markdown (mdHeading yellow, mdCode violet, mdCodeBlock green, mdLink blue).
hl(0, "markdownH1", { ctermfg = 3, cterm = { bold = true } })
hl(0, "markdownH2", { ctermfg = 3, cterm = { bold = true } })
hl(0, "markdownH3", { ctermfg = 3 })
hl(0, "markdownH4", { ctermfg = 3 })
hl(0, "markdownH5", { ctermfg = 3 })
hl(0, "markdownH6", { ctermfg = 3 })
hl(0, "markdownCode", { ctermfg = 5 })
hl(0, "markdownCodeBlock", { ctermfg = 2 })
hl(0, "markdownLinkText", { ctermfg = 4 })
hl(0, "markdownListMarker", { ctermfg = 5 })
hl(0, "helpHyperTextEntry", { ctermfg = 4 })
hl(0, "helpCommand", { ctermfg = 5 })

-- Treesitter groups (the ones that do not already link to a legacy group).
hl(0, "@keyword", { ctermfg = 4 })
hl(0, "@label", { ctermfg = 4 })
hl(0, "@string", { ctermfg = 2 })
hl(0, "@number", { ctermfg = 5 })
hl(0, "@boolean", { ctermfg = 5 })
hl(0, "@constant", { ctermfg = 5 })
hl(0, "@function", { ctermfg = 3 })
hl(0, "@type", { ctermfg = 5 })
hl(0, "@variable", { ctermfg = 6 })
hl(0, "@parameter", { ctermfg = 6 })
hl(0, "@property", { ctermfg = 6 })
hl(0, "@comment", {})
hl(0, "@operator", {})
hl(0, "@punctuation.bracket", {})
hl(0, "@punctuation.delimiter", {})
hl(0, "@markup.heading", { ctermfg = 3, cterm = { bold = true } })
hl(0, "@markup.link", { ctermfg = 4 })
hl(0, "@markup.raw", { ctermfg = 5 })
hl(0, "@markup.list", { ctermfg = 5 })
hl(0, "@diff.plus", { ctermfg = 2 })
hl(0, "@diff.minus", { ctermfg = 1 })
hl(0, "@diff.delta", { ctermfg = 3 })
