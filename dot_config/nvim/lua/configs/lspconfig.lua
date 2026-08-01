require("nvchad.configs.lspconfig").defaults()

vim.lsp.config("gopls", {
  settings = {
    gopls = {
      analyses = {
        unusedparams = true,
        unusedwrite = true,
      },
      staticcheck = true,
      gofumpt = true,
    },
  },
})

vim.lsp.config("pyright", {
  settings = {
    python = {
      analysis = {
        typeCheckingMode = "basic",
        autoImportCompletions = true,
      },
    },
  },
})

vim.lsp.config("jsonls", {
  settings = {
    json = {
      schemas = (function()
        local ok, schemastore = pcall(require, "schemastore")
        if ok then
          return schemastore.json.schemas()
        end
        return {}
      end)(),
      validate = { enable = true },
    },
  },
})

vim.lsp.enable {
  "gopls",
  "pyright",
  "ts_ls",
  "bashls",
  "jsonls",
  "yamlls",
  "html",
  "cssls",
}
