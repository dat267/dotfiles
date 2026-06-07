vim.api.nvim_create_autocmd("FileType", {
	pattern = { "javascript", "javascriptreact" },
	callback = function()
		local root_file = vim.fs.find({ "package.json", ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		vim.lsp.start({
			name = "typescript-language-server",
			cmd = { "typescript-language-server", "--stdio" },
			root_dir = root_dir,
		})
	end,
})

