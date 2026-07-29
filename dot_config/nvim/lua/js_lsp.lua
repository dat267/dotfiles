vim.api.nvim_create_autocmd("FileType", {
	pattern = { "javascript", "javascriptreact" },
	callback = function()
		local root_file = vim.fs.find({ "package.json", ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		local cmd = "typescript-language-server"
		if vim.fn.has("win32") == 1 then
			if vim.fn.executable("typescript-language-server.cmd") == 1 then
				cmd = "typescript-language-server.cmd"
			elseif vim.fn.executable("typescript-language-server.exe") == 1 then
				cmd = "typescript-language-server.exe"
			elseif vim.fn.executable("typescript-language-server.bat") == 1 then
				cmd = "typescript-language-server.bat"
			end
		end
		vim.lsp.start({
			name = "typescript-language-server",
			cmd = { cmd, "--stdio" },
			root_dir = root_dir,
		})
	end,
})

