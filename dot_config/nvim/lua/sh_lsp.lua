vim.api.nvim_create_autocmd("FileType", {
	pattern = { "sh", "bash" },
	callback = function()
		local root_file = vim.fs.find({ ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		local cmd = "bash-language-server"
		if vim.fn.has("win32") == 1 then
			if vim.fn.executable("bash-language-server.cmd") == 1 then
				cmd = "bash-language-server.cmd"
			elseif vim.fn.executable("bash-language-server.exe") == 1 then
				cmd = "bash-language-server.exe"
			elseif vim.fn.executable("bash-language-server.bat") == 1 then
				cmd = "bash-language-server.bat"
			end
		end
		vim.lsp.start({
			name = "bash-language-server",
			cmd = { cmd, "start" },
			root_dir = root_dir,
		})
	end,
})

