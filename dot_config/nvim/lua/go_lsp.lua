vim.api.nvim_create_autocmd("FileType", {
  pattern = "go",
  callback = function(event)
    local root_dir = vim.fs.root(event.buf, { "go.mod", ".git" }) or vim.uv.cwd()
    vim.lsp.start({
      name = "gopls",
      cmd = { "gopls" },
      root_dir = root_dir,
      settings = {
        gopls = {
          analyses = {
            unusedparams = true,
            shadow = true,
            nilness = true,
            unusedwrite = true,
            useany = true,
            appends = true,
            assign = true,
            composites = true,
            deepequalerrors = true,
            errorsas = true,
            httpresponse = true,
            loopclosure = true,
            lostcancel = true,
            printf = true,
            sigchanyzer = true,
            sortslice = true,
            testinggoroutine = true,
            timeformat = true,
          },
          staticcheck = true,
          gofumpt = true,
          usePlaceholders = true,
          completeUnimported = true,
          completeFunctionCalls = true,
          matcher = "Fuzzy",
          hints = {
            assignVariableTypes = true,
            compositeLiteralFields = true,
            compositeLiteralTypes = true,
            constantValues = false,
            functionTypeParameters = true,
            parameterNames = true,
            rangeVariableTypes = true,
          },
          linksInHover = true,
          semanticTokens = true,
          codelenses = {
            generate = true,
            test = true,
            tidy = true,
            upgrade_dependency = true,
            vendor = true,
          },
          templateExtensions = { "tmpl", "gotmpl" },
          directoryFilters = { "-.git", "-node_modules", "-vendor" },
        },
      },
    })
  end,
})

vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.go",
  callback = function(event)
    local params = vim.lsp.util.make_range_params(0, "utf-16")
    params.context = { Only = { "source.organizeImports" } }
    local result = vim.lsp.buf_request_sync(event.buf, "textDocument/codeAction", params, 1000)
    for _, res in pairs(result or {}) do
      for _, r in pairs(res.result or {}) do
        if r.edit then
          vim.lsp.util.apply_workspace_edit(r.edit, "utf-16")
        end
      end
    end
    vim.lsp.buf.format({ async = false, bufnr = event.buf })
  end,
})
