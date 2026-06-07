vim.api.nvim_create_autocmd("FileType", {
	pattern = "python",
	callback = function()
		local root_file = vim.fs.find({ "pyproject.toml", "setup.py", "requirements.txt", ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		vim.lsp.start({
			name = "pyright",
			cmd = { "pyright-langserver", "--stdio" },
			root_dir = root_dir,
			settings = {
				python = {
					analysis = {
						autoSearchPaths = true,
						useLibraryCodeForTypes = true,
						diagnosticMode = "openFilesOnly",
					},
				},
			},
		})
	end,
})

