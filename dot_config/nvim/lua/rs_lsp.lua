vim.api.nvim_create_autocmd("FileType", {
    pattern = "rust",
    callback = function(args)
    local root_markers = { "Cargo.toml", ".git" }
    local root_dir = vim.fs.root(args.buf, root_markers) or vim.fn.getcwd()

    vim.lsp.start({
        name = "rust-analyzer",
        cmd = { "rust-analyzer" },
        root_dir = root_dir,
        settings = {
            ["rust-analyzer"] = {
                cargo = {
                    buildScripts = {
                        enable = true,
                    },
                },
                procMacro = {
                    enable = true,
                },
            },
        },
    }, { bufnr = args.buf })
    end,
})
