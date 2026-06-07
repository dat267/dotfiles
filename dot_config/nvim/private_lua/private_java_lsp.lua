vim.api.nvim_create_autocmd("FileType", {
  pattern = "java",
  callback = function(args)
    local root_markers = { ".git", "mvnw", "gradlew", "pom.xml", "build.gradle" }
    local root_dir = vim.fs.root(args.buf, root_markers)
    if not root_dir then return end

    local workspace = vim.fn.stdpath("cache") .. "/jdtls-workspace/" .. vim.fn.fnamemodify(root_dir, ":t")

    vim.lsp.start({
      name = "jdtls",
      cmd = { "jdtls", "-data", workspace },
      root_dir = root_dir,
    }, { bufnr = args.buf })
  end,
})
