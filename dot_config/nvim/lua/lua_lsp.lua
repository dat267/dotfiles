vim.api.nvim_create_autocmd("FileType", {
	pattern = "lua",
	callback = function()
		local root_file = vim.fs.find({ ".git", "init.lua" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		vim.lsp.start({
			name = "lua-language-server",
			cmd = { "lua-language-server" },
			root_dir = root_dir,
			settings = {
				Lua = {
					runtime = {
						version = "LuaJIT",
					},
					diagnostics = {
						globals = { "vim" },
					},
					workspace = {
						library = vim.api.nvim_get_runtime_file("", true),
						checkThirdParty = false,
					},
					telemetry = {
						enable = false,
					},
				},
			},
		})
	end,
})

