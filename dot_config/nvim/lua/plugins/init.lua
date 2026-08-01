return {
  {
    "neovim/nvim-lspconfig",
    config = function()
      require "configs.lspconfig"
    end,
  },

  {
    "stevearc/conform.nvim",
    opts = {
      formatters_by_ft = {
        lua = { "stylua" },
        go = { "gofumpt", "goimports" },
        python = { "ruff_format" },
        javascript = { "prettierd", "prettier", stop_after_first = true },
        typescript = { "prettierd", "prettier", stop_after_first = true },
        json = { "prettierd", "prettier", stop_after_first = true },
        yaml = { "yamlfmt" },
        bash = { "shfmt" },
      },
      format_on_save = {
        timeout_ms = 1500,
        lsp_format = "fallback",
      },
    },
  },

  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = {
        "lua",
        "vim",
        "vimdoc",
        "go",
        "gomod",
        "python",
        "typescript",
        "tsx",
        "javascript",
        "json",
        "yaml",
        "bash",
        "html",
        "css",
        "markdown",
        "markdown_inline",
        "regex",
      },
    },
  },

  {
    "mfussenegger/nvim-dap",
    config = function()
      require "configs.dap"
    end,
    dependencies = {
      {
        "rcarriga/nvim-dap-ui",
        dependencies = { "nvim-neotest/nvim-nio" },
      },
      "theHamsta/nvim-dap-virtual-text",
      {
        "williamboman/mason-nvim-dap.nvim",
        dependencies = { "williamboman/mason.nvim" },
        opts = {
          ensure_installed = { "delve", "debugpy", "codelldb" },
          automatic_installation = true,
        },
      },
    },
  },
}
