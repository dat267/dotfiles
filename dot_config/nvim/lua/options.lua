require "nvchad.options"

local o = vim.o

if vim.env.SSH_TTY then
  vim.g.clipboard = {
    name = "OSC 52",
    copy = {
      ["+"] = require("vim.ui.clipboard.osc52").copy("+"),
      ["*"] = require("vim.ui.clipboard.osc52").copy("*"),
    },
    paste = {
      ["+"] = function()
        return vim.fn.split(vim.fn.getreg(""), "\n")
      end,
      ["*"] = function()
        return vim.fn.split(vim.fn.getreg(""), "\n")
      end,
    },
  }
end

o.scrolloff = 8
o.inccommand = "split"
o.relativenumber = true
o.tabstop = 4
o.shiftwidth = 4
o.softtabstop = 4
o.expandtab = true
o.smartindent = true

local opt = vim.opt

o.list = true
opt.listchars = { tab = "» ", trail = "·", nbsp = "␣" }
