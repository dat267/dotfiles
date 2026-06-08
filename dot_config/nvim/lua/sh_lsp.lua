vim.api.nvim_create_autocmd("FileType", {
	pattern = { "sh", "bash" },
	callback = function()
		local root_file = vim.fs.find({ ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		vim.lsp.start({
			name = "bash-language-server",
			cmd = { "bash-language-server", "start" },
			root_dir = root_dir,
		})
	end,
})

