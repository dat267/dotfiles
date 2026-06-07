vim.api.nvim_create_autocmd("FileType", {
	pattern = "markdown",
	callback = function()
		local root_file = vim.fs.find({ ".git", ".marksman.toml" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		vim.lsp.start({
			name = "marksman",
			cmd = { "marksman", "server" },
			root_dir = root_dir,
		})
	end,
})
