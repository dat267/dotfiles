local opt = vim.opt

-- Wrap the cursor across line boundaries with h/l and arrow keys
opt.whichwrap:append("h,l,<,>,[,]")

opt.number = true
opt.relativenumber = true
opt.scrolloff = 8
opt.inccommand = "split"

-- Show the completion menu without auto-inserting the first item
opt.completeopt = "menu,menuone,noselect"

opt.tabstop = 4
opt.shiftwidth = 4
opt.softtabstop = 4
opt.expandtab = true
opt.smartindent = true

opt.list = true
opt.listchars = { tab = "» ", trail = "·", nbsp = "␣" }

opt.mouse = "a"
opt.splitright = true
opt.splitbelow = true
opt.ignorecase = true
opt.smartcase = true
opt.hlsearch = true
-- Soft-wrap long lines at word boundaries
opt.wrap = true
opt.linebreak = true
opt.signcolumn = "yes"
opt.updatetime = 250
opt.undofile = true
opt.swapfile = false
opt.clipboard = "unnamedplus"

local autocmd = vim.api.nvim_create_autocmd

-- Follow the terminal's theme instead of forcing one. Don't override the
-- 'background' the TUI sets (from the terminal's own report when it answers
-- OSC 11, else the default); clearing Normal's background lets the terminal's
-- own color show instead of the colorscheme's. Re-apply after the scheme
-- reloads with 'background' (OptionSet fires after startup) and on live theme
-- changes (DEC mode 2031).
local function use_terminal_background()
  vim.api.nvim_set_hl(0, "Normal", { bg = "none", ctermbg = "none" })
end
use_terminal_background()
autocmd("ColorScheme", { callback = use_terminal_background })
autocmd("OptionSet", {
  pattern = "background",
  callback = function()
    vim.schedule(use_terminal_background)
  end,
})
autocmd("OptionSet", {
  pattern = "clipboard",
  callback = function()
    vim.opt.clipboard:append "unnamedplus"
  end,
})

if vim.env.SSH_TTY then
  -- OSC 52 clipboard: Termux garbles the editor when the base64 payload
  -- exceeds its buffer (~64KB is safe). Larger yanks stay in the Neovim
  -- register (pasteable with p / "0p). The size is measured on the base64
  -- payload actually transmitted (lines joined with "\n", then encoded),
  -- which expands ~4/3 over the raw bytes.
  local max_osc52_payload = 64 * 1024
  local function osc52_copy(reg)
    return function(lines)
      local payload = vim.base64.encode(table.concat(lines, "\n"))
      if #payload <= max_osc52_payload then
        return require("vim.ui.clipboard.osc52").copy(reg)(lines)
      end
    end
  end
  vim.g.clipboard = {
    name = "OSC 52",
    copy = {
      ["+"] = osc52_copy("+"),
      ["*"] = osc52_copy("*"),
    },
    paste = {
      ["+"] = function()
        return vim.fn.split(vim.fn.getreg(), "\n")
      end,
      ["*"] = function()
        return vim.fn.split(vim.fn.getreg(), "\n")
      end,
    },
  }
end
