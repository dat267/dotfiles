vim.api.nvim_create_autocmd("FileType", {
	pattern = "python",
	callback = function()
		local root_file = vim.fs.find({ "pyproject.toml", "setup.py", "requirements.txt", ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		local cmd = "pyright-langserver"
		if vim.fn.has("win32") == 1 then
			if vim.fn.executable("pyright-langserver.cmd") == 1 then
				cmd = "pyright-langserver.cmd"
			elseif vim.fn.executable("pyright-langserver.exe") == 1 then
				cmd = "pyright-langserver.exe"
			elseif vim.fn.executable("pyright-langserver.bat") == 1 then
				cmd = "pyright-langserver.bat"
			end
		end
		vim.lsp.start({
			name = "pyright",
			cmd = { cmd, "--stdio" },
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

vim.api.nvim_create_autocmd("BufWritePre", {
	pattern = "*.py",
	callback = function()
		local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
		local current_text = table.concat(lines, "\n")
		local result = vim.system({ "black", "-q", "-" }, { stdin = current_text }):wait()
		if result.code == 0 then
			local new_lines = vim.split(result.stdout, "\n")
			if new_lines[#new_lines] == "" then
				table.remove(new_lines)
			end
			local view = vim.fn.winsaveview()
			vim.api.nvim_buf_set_lines(0, 0, -1, false, new_lines)
			vim.fn.winrestview(view)
		end
	end,
})

