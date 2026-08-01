local dap = require "dap"
local dapui = require "dapui"

local map = vim.keymap.set

map("n", "<leader>dl", dap.continue, { desc = "debug continue" })
map("n", "<leader>db", dap.toggle_breakpoint, { desc = "debug toggle breakpoint" })
map("n", "<leader>dc", function()
  dap.set_breakpoint(vim.fn.input "Breakpoint condition: ")
end, { desc = "debug conditional breakpoint" })
map("n", "<leader>do", dap.step_over, { desc = "debug step over" })
map("n", "<leader>di", dap.step_into, { desc = "debug step into" })
map("n", "<leader>dO", dap.step_out, { desc = "debug step out" })
map("n", "<leader>du", dapui.toggle, { desc = "debug toggle ui" })
map("n", "<leader>dr", dap.repl.toggle, { desc = "debug repl" })

dapui.setup {
  layouts = {
    {
      elements = {
        { id = "scopes", size = 0.3 },
        { id = "breakpoints", size = 0.2 },
        { id = "watches", size = 0.2 },
        { id = "stacks", size = 0.3 },
      },
      size = 0.4,
      position = "left",
    },
    {
      elements = {
        { id = "repl", size = 0.5 },
        { id = "console", size = 0.5 },
      },
      size = 0.25,
      position = "bottom",
    },
  },
  floating = {
    border = "rounded",
  },
}

dap.listeners.after.event_initialized["dapui_config"] = dapui.open
dap.listeners.before.event_terminated["dapui_config"] = dapui.close
dap.listeners.before.event_exited["dapui_config"] = dapui.close

dap.adapters.go = function(callback, config)
  local port = require("dap.utils").pick_port()
  local dlv = vim.fn.stdpath "data" .. "/mason/bin/dlv"
  if vim.fn.executable(dlv) == 0 then
    dlv = "dlv"
  end
  vim.fn.jobstart({ dlv, "dap", "-l", "127.0.0.1:" .. port }, { detach = true })
  vim.defer_fn(function()
    callback({
      type = "server",
      host = "127.0.0.1",
      port = port,
    })
  end, 100)
end

dap.configurations.go = {
  {
    type = "go",
    name = "Debug file",
    request = "launch",
    program = "${file}",
  },
  {
    type = "go",
    name = "Debug test",
    request = "launch",
    mode = "test",
    program = "${file}",
  },
  {
    type = "go",
    name = "Debug package",
    request = "launch",
    mode = "auto",
    program = "${fileDirname}",
  },
}

dap.adapters.python = {
  type = "executable",
  command = vim.fn.stdpath "data" .. "/mason/packages/debugpy/venv/bin/python",
  args = { "-m", "debugpy.adapter" },
}

dap.configurations.python = {
  {
    type = "python",
    name = "Debug file",
    request = "launch",
    program = "${file}",
    console = "integratedTerminal",
  },
}

dap.adapters.codelldb = function(callback, config)
  local port = require("dap.utils").pick_port()
  local exe = vim.fn.stdpath "data" .. "/mason/bin/codelldb"
  vim.fn.jobstart({ exe, "--port", tostring(port) }, { detach = true })
  vim.defer_fn(function()
    callback({
      type = "server",
      host = "127.0.0.1",
      port = port,
    })
  end, 100)
end

dap.configurations.c = {
  {
    type = "codelldb",
    name = "Launch",
    request = "launch",
    program = function()
      return vim.fn.input("Path to executable: ", vim.fn.getcwd() .. "/", "file")
    end,
    cwd = "${workspaceFolder}",
    stopOnEntry = false,
    args = {},
  },
}

dap.configurations.cpp = dap.configurations.c
dap.configurations.rust = dap.configurations.c

require("nvim-dap-virtual-text").setup()
