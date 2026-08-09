# Design: Expand `{}` block on `<CR>` for Neovim

Date: 2026-08-09
Status: Approved

## Goal

When the cursor sits in an empty auto-paired `{}` and the user presses
`<CR>` in insert mode, expand into a three-line block with the cursor
centered and indented one level.

## Behavior

```
func main() {|        -- cursor between braces, press <CR>
```
becomes

```
func main() {
    |                -- cursor on the middle line, indented shiftwidth
}
```

## Implementation

`dot_config/nvim/lua/brackets.lua`: an insert-mode `<CR>` keymap.

- If `char_before_cursor() == "{"` and `char_after_cursor() == "}"`:
  1. `base_indent = current_line:match("^%s*")` (leading whitespace).
  2. `indent_unit = expandtab ? string.rep(" ", shiftwidth) : "\t"`.
  3. `middle = base_indent .. indent_unit`.
  4. `nvim_buf_set_text(row-1, col, row-1, col+1, { "", middle, base_indent .. "}" })`
     — replaces the `}` (at the cursor column) with the three lines; any text
     after the `}` (e.g. `;`) stays on the last line.
  5. Position the cursor on the middle line via
     `<C-o>:call cursor(row+1, #middle+1)` fed with `"in"` (matches the file's
     existing feedkeys style; reliable in insert mode).
- Otherwise fall through to the native `<CR>`, fed with no-remap
  (`nvim_feedkeys("<CR>", "in")`) so the mapping does not recurse.

## Scope

- `{` only. `(` and `[` keep normal `<CR>`.
- Applies whenever an empty `{}` pair is under the cursor, regardless of what
  precedes (`func main() {}`) or follows (`{};`) the braces.
- Respects `expandtab`/`shiftwidth` for the middle-line indent; `}` aligns to
  the current line's leading indent.

## Verification

Headless (nvim 0.12.4):
1. Config smoke.
2. Buffer transformation: `func main() {}` with cursor between braces →
   three lines (`func main() {`, `    `, `}`), cursor on line 2 at the end of
   the indent.
3. Trailing content preserved (`{};` → last line `};`).
4. Non-pair `<CR>` (e.g. cursor not inside `{}`) does not expand (falls
   through — no error, buffer unchanged by the mapping's expansion branch).
5. Manual: live insert-mode cursor positioning on the user machine.

## Files touched

- `dot_config/nvim/lua/brackets.lua`
