local M = {}

local palettes = {
  dark = {
    bg         = "#1F1F1F",
    bg_alt     = "#282C34",
    bg_float   = "#2C323C",
    fg         = "#DCDFE4",
    fg_alt     = "#ABB2BF",
    comment    = "#808080",
    selection  = "#3E4452",
    line_nr    = "#5C6370",
    cursorline = "#2C323C",
    nontext    = "#4B5263",
    red        = "#E06C75",
    orange     = "#E45649",
    green      = "#98C379",
    yellow     = "#E5C07B",
    blue       = "#61AFEF",
    purple     = "#C678DD",
    cyan       = "#56B6C2",
    white      = "#FFFFFF",
    error_red  = "#E06C75",
    warn_yell  = "#E5C07B",
    info_blue  = "#61AFEF",
    hint_gray  = "#808080",
    git_add    = "#98C379",
    git_change = "#E5C07B",
    git_delete = "#E06C75",
  },
  light = {
    bg         = "#F3F3F3",
    bg_alt     = "#FAFAFA",
    bg_float   = "#FFFFFF",
    fg         = "#383A42",
    fg_alt     = "#696C77",
    comment    = "#A0A1A7",
    selection  = "#E5E5E5",
    line_nr    = "#9D9D9F",
    cursorline = "#E8E8E8",
    nontext    = "#C0C0C0",
    red        = "#E45649",
    orange     = "#D75F00",
    green      = "#50A14F",
    yellow     = "#C18301",
    blue       = "#0184BC",
    purple     = "#A626A4",
    cyan       = "#0997B3",
    white      = "#000000",
    error_red  = "#E45649",
    warn_yell  = "#C18301",
    info_blue  = "#0184BC",
    hint_gray  = "#A0A1A7",
    git_add    = "#50A14F",
    git_change = "#C18301",
    git_delete = "#E45649",
  },
}

function M.setup(mode)
  mode = mode or "dark"
  local c = palettes[mode]
  if not c then c = palettes.dark end

  vim.g.colors_name = "theme_" .. mode
  vim.o.background = mode

  local hl = vim.api.nvim_set_hl

  hl(0, "Normal",             { fg = c.fg, bg = c.bg })
  hl(0, "NormalFloat",        { fg = c.fg, bg = c.bg_float })
  hl(0, "EndOfBuffer",        { fg = c.nontext, bg = c.bg })
  hl(0, "NonText",            { fg = c.nontext })
  hl(0, "Whitespace",         { fg = c.nontext })
  hl(0, "Conceal",            { fg = c.comment })
  hl(0, "SpecialKey",         { fg = c.comment })

  hl(0, "Cursor",             { fg = c.bg, bg = c.fg })
  hl(0, "CursorLine",         { bg = c.cursorline })
  hl(0, "CursorColumn",       { bg = c.cursorline })
  hl(0, "CursorLineNr",       { fg = c.fg, bg = c.cursorline, bold = true })
  hl(0, "LineNr",             { fg = c.line_nr })
  hl(0, "CursorLineFold",     { fg = c.comment })
  hl(0, "CursorLineSign",     { bg = c.cursorline })

  hl(0, "Visual",             { bg = c.selection })
  hl(0, "VisualNOS",          { bg = c.selection, underline = true })

  hl(0, "Search",             { fg = c.yellow, bg = c.bg, reverse = true, bold = true })
  hl(0, "IncSearch",          { fg = c.bg, bg = c.yellow, bold = true })
  hl(0, "CurSearch",          { link = "IncSearch" })

  hl(0, "StatusLine",         { fg = c.fg, bg = c.bg_alt, bold = true })
  hl(0, "StatusLineNC",       { fg = c.comment, bg = c.bg_alt })
  hl(0, "WinSeparator",       { fg = c.nontext })
  hl(0, "VertSplit",          { link = "WinSeparator" })

  hl(0, "TabLine",            { fg = c.comment, bg = c.bg_alt })
  hl(0, "TabLineFill",        { bg = c.bg_alt })
  hl(0, "TabLineSel",         { fg = c.fg, bg = c.bg, bold = true })

  hl(0, "Pmenu",              { fg = c.fg, bg = c.bg_float })
  hl(0, "PmenuSel",           { fg = c.bg, bg = c.blue, bold = true })
  hl(0, "PmenuSbar",          { bg = c.bg_alt })
  hl(0, "PmenuThumb",         { bg = c.comment })

  hl(0, "ErrorMsg",           { fg = c.error_red, bold = true })
  hl(0, "WarningMsg",         { fg = c.warn_yell, bold = true })
  hl(0, "MoreMsg",            { fg = c.blue, bold = true })
  hl(0, "ModeMsg",            { fg = c.fg, bold = true })
  hl(0, "Question",           { fg = c.blue, bold = true })

  hl(0, "DiffAdd",            { fg = c.git_add, bg = c.bg_alt })
  hl(0, "DiffChange",         { fg = c.git_change, bg = c.bg_alt })
  hl(0, "DiffDelete",         { fg = c.git_delete, bg = c.bg_alt })
  hl(0, "DiffText",           { fg = c.bg, bg = c.cyan })

  hl(0, "Folded",             { fg = c.comment, bg = c.bg_alt })
  hl(0, "FoldColumn",         { fg = c.comment, bg = c.bg })

  hl(0, "SpellBad",           { undercurl = true, sp = c.error_red })
  hl(0, "SpellCap",           { undercurl = true, sp = c.blue })
  hl(0, "SpellLocal",         { undercurl = true, sp = c.cyan })
  hl(0, "SpellRare",          { undercurl = true, sp = c.purple })

  hl(0, "Comment",            { fg = c.comment, italic = true })
  hl(0, "Constant",           { fg = c.orange })
  hl(0, "String",             { fg = c.green })
  hl(0, "Character",          { fg = c.green })
  hl(0, "Number",             { fg = c.orange })
  hl(0, "Boolean",            { fg = c.orange })
  hl(0, "Float",              { fg = c.orange })
  hl(0, "Function",           { fg = c.yellow })
  hl(0, "Identifier",         { fg = c.red })
  hl(0, "Keyword",            { fg = c.purple, italic = true })
  hl(0, "Statement",          { fg = c.purple })
  hl(0, "Conditional",        { fg = c.purple, italic = true })
  hl(0, "Repeat",             { fg = c.purple })
  hl(0, "Label",              { fg = c.purple })
  hl(0, "Operator",           { fg = c.cyan })
  hl(0, "Exception",          { fg = c.purple })
  hl(0, "Include",            { fg = c.blue })
  hl(0, "Define",             { fg = c.purple })
  hl(0, "Macro",              { fg = c.purple })
  hl(0, "PreProc",            { fg = c.blue })
  hl(0, "PreCondit",          { fg = c.yellow })
  hl(0, "Type",               { fg = c.blue })
  hl(0, "StorageClass",       { fg = c.purple, italic = true })
  hl(0, "Structure",          { fg = c.cyan })
  hl(0, "Typedef",            { fg = c.blue })
  hl(0, "Special",            { fg = c.cyan })
  hl(0, "SpecialChar",        { fg = c.cyan })
  hl(0, "Tag",                { fg = c.yellow })
  hl(0, "Delimiter",          { fg = c.fg_alt })
  hl(0, "Debug",              { fg = c.yellow })
  hl(0, "Underlined",         { underline = true, sp = c.blue })
  hl(0, "Bold",               { bold = true })
  hl(0, "Italic",             { italic = true })
  hl(0, "Title",              { fg = c.blue, bold = true })

  hl(0, "DiagnosticError",            { fg = c.error_red })
  hl(0, "DiagnosticWarn",             { fg = c.warn_yell })
  hl(0, "DiagnosticInfo",             { fg = c.info_blue })
  hl(0, "DiagnosticHint",             { fg = c.hint_gray })
  hl(0, "DiagnosticOk",               { fg = c.git_add })
  hl(0, "DiagnosticUnderlineError",   { undercurl = true, sp = c.error_red })
  hl(0, "DiagnosticUnderlineWarn",    { undercurl = true, sp = c.warn_yell })
  hl(0, "DiagnosticUnderlineInfo",    { undercurl = true, sp = c.info_blue })
  hl(0, "DiagnosticUnderlineHint",    { undercurl = true, sp = c.hint_gray })
  hl(0, "DiagnosticSignError",        { fg = c.error_red })
  hl(0, "DiagnosticSignWarn",         { fg = c.warn_yell })
  hl(0, "DiagnosticSignInfo",         { fg = c.info_blue })
  hl(0, "DiagnosticSignHint",         { fg = c.hint_gray })
  hl(0, "DiagnosticFloatingError",    { fg = c.error_red })
  hl(0, "DiagnosticFloatingWarn",     { fg = c.warn_yell })
  hl(0, "DiagnosticFloatingInfo",     { fg = c.info_blue })
  hl(0, "DiagnosticFloatingHint",     { fg = c.hint_gray })
  hl(0, "DiagnosticVirtualTextError", { fg = c.error_red })
  hl(0, "DiagnosticVirtualTextWarn",  { fg = c.warn_yell })
  hl(0, "DiagnosticVirtualTextInfo",  { fg = c.info_blue })
  hl(0, "DiagnosticVirtualTextHint",  { fg = c.hint_gray })

  hl(0, "@comment",               { link = "Comment" })
  hl(0, "@error",                 { fg = c.error_red })
  hl(0, "@none",                  {})
  hl(0, "@preproc",               { link = "PreProc" })
  hl(0, "@define",                { link = "Define" })
  hl(0, "@operator",              { link = "Operator" })
  hl(0, "@punctuation.delimiter", { link = "Delimiter" })
  hl(0, "@punctuation.bracket",   { fg = c.fg_alt })
  hl(0, "@punctuation.special",   { fg = c.cyan })
  hl(0, "@string",                { link = "String" })
  hl(0, "@string.regex",          { fg = c.cyan })
  hl(0, "@string.escape",         { fg = c.cyan })
  hl(0, "@string.special",        { fg = c.cyan })
  hl(0, "@character",             { link = "Character" })
  hl(0, "@character.special",     { fg = c.cyan })
  hl(0, "@boolean",               { link = "Boolean" })
  hl(0, "@number",                { link = "Number" })
  hl(0, "@float",                 { link = "Float" })
  hl(0, "@function",              { link = "Function" })
  hl(0, "@function.builtin",      { fg = c.blue })
  hl(0, "@function.call",         { link = "Function" })
  hl(0, "@function.macro",        { link = "Macro" })
  hl(0, "@function.method",       { link = "Function" })
  hl(0, "@function.method.call",  { link = "Function" })
  hl(0, "@parameter",             { fg = c.red })
  hl(0, "@parameter.reference",   { fg = c.red })
  hl(0, "@method",                { link = "Function" })
  hl(0, "@method.call",           { link = "Function" })
  hl(0, "@field",                 { fg = c.blue })
  hl(0, "@property",              { fg = c.cyan })
  hl(0, "@constructor",           { fg = c.orange })
  hl(0, "@conditional",           { link = "Conditional" })
  hl(0, "@repeat",                { link = "Repeat" })
  hl(0, "@label",                 { link = "Label" })
  hl(0, "@include",               { link = "Include" })
  hl(0, "@exception",             { link = "Exception" })
  hl(0, "@keyword",               { link = "Keyword" })
  hl(0, "@keyword.function",      { fg = c.purple })
  hl(0, "@keyword.operator",      { fg = c.purple })
  hl(0, "@keyword.return",        { link = "Keyword" })
  hl(0, "@type",                  { link = "Type" })
  hl(0, "@type.builtin",          { fg = c.blue })
  hl(0, "@type.definition",       { link = "Typedef" })
  hl(0, "@type.qualifier",        { link = "StorageClass" })
  hl(0, "@storageclass",          { link = "StorageClass" })
  hl(0, "@attribute",             { fg = c.yellow })
  hl(0, "@variable",              { fg = c.fg })
  hl(0, "@variable.builtin",      { fg = c.red })
  hl(0, "@constant",              { link = "Constant" })
  hl(0, "@constant.builtin",      { fg = c.orange })
  hl(0, "@constant.macro",        { fg = c.orange })
  hl(0, "@namespace",             { fg = c.cyan })
  hl(0, "@symbol",                { fg = c.cyan })
  hl(0, "@text",                  { fg = c.fg })
  hl(0, "@text.title",            { fg = c.blue, bold = true })
  hl(0, "@text.uri",              { fg = c.blue, underline = true })
  hl(0, "@text.underline",        { underline = true })
  hl(0, "@text.strong",           { bold = true })
  hl(0, "@text.emphasis",         { italic = true })
  hl(0, "@text.strike",           { strikethrough = true })
  hl(0, "@text.math",             { fg = c.cyan })
  hl(0, "@tag",                   { fg = c.yellow })
  hl(0, "@tag.attribute",         { fg = c.cyan })
  hl(0, "@tag.delimiter",         { fg = c.comment })

  hl(0, "GitSignsAdd",           { fg = c.git_add })
  hl(0, "GitSignsChange",        { fg = c.git_change })
  hl(0, "GitSignsDelete",        { fg = c.git_delete })
  hl(0, "GitSignsAddNr",         { link = "GitSignsAdd" })
  hl(0, "GitSignsChangeNr",      { link = "GitSignsChange" })
  hl(0, "GitSignsDeleteNr",      { link = "GitSignsDelete" })
  hl(0, "GitGutterAdd",          { link = "GitSignsAdd" })
  hl(0, "GitGutterChange",       { link = "GitSignsChange" })
  hl(0, "GitGutterDelete",       { link = "GitSignsDelete" })
  hl(0, "MiniDiffSignAdd",       { link = "GitSignsAdd" })
  hl(0, "MiniDiffSignChange",    { link = "GitSignsChange" })
  hl(0, "MiniDiffSignDelete",    { link = "GitSignsDelete" })

  hl(0, "LspReferenceText",      { bg = c.selection })
  hl(0, "LspReferenceRead",      { bg = c.selection })
  hl(0, "LspReferenceWrite",     { bg = c.selection })
  hl(0, "LspInlayHint",          { fg = c.comment, bg = c.bg_alt })

  hl(0, "HealthError",           { fg = c.error_red })
  hl(0, "HealthSuccess",         { fg = c.git_add })
  hl(0, "HealthWarning",         { fg = c.warn_yell })
end

return M
