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
opt.wrap = false
opt.signcolumn = "yes"
opt.updatetime = 250
opt.undofile = true
opt.swapfile = false
opt.clipboard = "unnamedplus"

-- Explicit background (supplemented by NVIM_NOTTYFAST env var for E1568)
opt.background = "dark"

local autocmd = vim.api.nvim_create_autocmd
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
