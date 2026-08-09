-- LSP via Neovim's built-in client (no plugin). Servers must be installed
-- system-wide. vim.lsp.config + vim.lsp.enable is the native 0.11+ API.

local servers = {
  gopls = {
    filetypes = { "go", "gomod" },
    cmd = { "gopls" },
    settings = {
      gopls = {
        analyses = { unusedparams = true, unusedwrite = true },
        staticcheck = true,
        gofumpt = true,
      },
    },
  },
  pyright = {
    filetypes = { "python" },
    cmd = { "pyright-langserver", "--stdio" },
    settings = {
      python = {
        analysis = {
          typeCheckingMode = "basic",
          autoImportCompletions = true,
        },
      },
    },
  },
  ts_ls = {
    filetypes = { "javascript", "javascriptreact", "typescript", "typescriptreact" },
    cmd = { "typescript-language-server", "--stdio" },
    enabled = false,
  },
  bashls = {
    filetypes = { "sh", "bash", "zsh" },
    cmd = { "bash-language-server", "start" },
  },
  jsonls = {
    filetypes = { "json", "jsonc" },
    cmd = { "vscode-json-language-server", "--stdio" },
    settings = {
      json = { validate = { enable = true } },
    },
  },
  yamlls = {
    filetypes = { "yaml", "yml" },
    cmd = { "yaml-language-server", "--stdio" },
  },
  html = {
    filetypes = { "html" },
    cmd = { "vscode-html-language-server", "--stdio" },
  },
  cssls = {
    filetypes = { "css", "scss", "less" },
    cmd = { "vscode-css-language-server", "--stdio" },
  },
  lua_ls = {
    filetypes = { "lua" },
    cmd = { "lua-language-server" },
    settings = {
      Lua = {
        workspace = { checkThirdParty = false },
        telemetry = { enable = false },
      },
    },
  },
  rust_analyzer = {
    filetypes = { "rust" },
    cmd = { "rust-analyzer" },
  },
}

for name, cfg in pairs(servers) do
  vim.lsp.config(name, cfg)
end

-- Only enable servers whose binary is actually installed, so loading a file
-- with a missing LSP never errors or spams startup messages. Configs with
-- `enabled = false` are skipped entirely.
local enabled = {}
for name, cfg in pairs(servers) do
  if cfg.enabled ~= false then
    local cmd = cfg.cmd or {}
    if #cmd > 0 and vim.fn.executable(cmd[1]) == 1 then
      enabled[#enabled + 1] = name
    end
  end
end
vim.lsp.enable(enabled)

-- LSP keymaps (applied when a client attaches)
local autocmd = vim.api.nvim_create_autocmd
autocmd("LspAttach", {
  callback = function(args)
    local bufnr = args.buf
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    local map = function(keys, fn, desc)
      vim.keymap.set("n", keys, fn, { buffer = bufnr, desc = desc })
    end

    map("gd", vim.lsp.buf.definition, "goto definition")
    map("gD", vim.lsp.buf.type_definition, "goto type definition")
    map("gI", vim.lsp.buf.implementation, "goto implementation")
    map("K", vim.lsp.buf.hover, "hover")
    map("<leader>rn", vim.lsp.buf.rename, "rename")
    map("<leader>ca", vim.lsp.buf.code_action, "code action")
    map("gr", vim.lsp.buf.references, "references")
    local function open_float_on_jump(_, bufnr)
      if bufnr then
        vim.diagnostic.open_float(bufnr, { focusable = false })
      end
    end
    map("[d", function()
      vim.diagnostic.jump({ count = -1, on_jump = open_float_on_jump })
    end, "prev diagnostic")
    map("]d", function()
      vim.diagnostic.jump({ count = 1, on_jump = open_float_on_jump })
    end, "next diagnostic")
    map("<leader>d", vim.diagnostic.open_float, "diagnostic float")

    -- On-type completion (native, no plugin): extend the server's trigger
    -- characters with identifier characters so the completion menu appears as
    -- you type, then enable autotrigger. gopls ships only ".", so without
    -- extension on-type would never fire for identifiers. <C-Space> manual
    -- completion was replaced by this; <C-x><C-o> stays available via omnifunc.
    if client and client:supports_method("textDocument/completion") then
      local provider = vim.tbl_get(client.server_capabilities, "completionProvider")
      if provider then
        provider.triggerCharacters = require("snippets").merge_trigger_chars(provider.triggerCharacters)
        vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })
      end
    end

    vim.bo[bufnr].omnifunc = "v:lua.vim.lsp.omnifunc"
  end,
})

-- Inlay hints on by default
vim.lsp.inlay_hint.enable(true, nil)

-- Diagnostics: full message in a bounded float (never clipped), capped to
-- 60% terminal width / 40% height. No inline virtual text or virtual lines.
vim.diagnostic.config({
  virtual_text = false,
  signs = true,
  update_in_insert = false,
  float = {
    border = "rounded",
    source = true,
    max_width = math.floor(vim.o.columns * 0.6),
    max_height = math.floor(vim.o.lines * 0.4),
  },
})

-- Auto-open the diagnostic float (bounded box) when pausing on a line that
-- has issues. <leader>d still opens it manually.
vim.api.nvim_create_autocmd("CursorHold", {
  callback = function()
    vim.diagnostic.open_float(nil, { focusable = false })
  end,
})

-- <Esc> dismisses an open diagnostic float.
vim.keymap.set("n", "<Esc>", function()
  if vim.fn.mode() == "n" then
    local floats = vim.tbl_filter(function(w)
      return vim.api.nvim_win_get_config(w).relative ~= ""
    end, vim.api.nvim_list_wins())
    if #floats > 0 then
      for _, w in ipairs(floats) do
        vim.api.nvim_win_close(w, false)
      end
      return
    end
  end
  return "<Esc>"
end, { expr = true, desc = "dismiss diagnostic float" })
