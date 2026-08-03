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
    local map = function(keys, fn, desc)
      vim.keymap.set("n", keys, fn, { buffer = bufnr, desc = desc })
    end

    map("gd", vim.lsp.buf.definition, "goto definition")
    map("K", vim.lsp.buf.hover, "hover")
    map("<leader>rn", vim.lsp.buf.rename, "rename")
    map("<leader>ca", vim.lsp.buf.code_action, "code action")
    map("gr", vim.lsp.buf.references, "references")
    map("[d", vim.diagnostic.goto_prev, "prev diagnostic")
    map("]d", vim.diagnostic.goto_next, "next diagnostic")
    map("<leader>d", vim.diagnostic.open_float, "diagnostic float")

    -- Manual omni-completion intellisense (no plugin): <C-Space> in insert
    -- mode triggers LSP completion; <C-n>/<C-p> continue keyword completion.
    vim.keymap.set("i", "<C-Space>", "<C-x><C-o>", { buffer = bufnr, desc = "LSP omni-completion" })

    vim.api.nvim_buf_set_option(bufnr, "omnifunc", "v:lua.vim.lsp.omnifunc")
  end,
})

-- Inlay hints on by default
vim.lsp.inlay_hint.enable(true, nil)
