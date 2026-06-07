vim.api.nvim_create_autocmd("FileType", {
	pattern = { "ps1", "psm1" },
	callback = function()
		local root_file = vim.fs.find({ ".git" }, { upward = true })[1]
		local root_dir = root_file and vim.fs.dirname(root_file) or vim.fn.getcwd()
		local bundle_path = vim.fn.expand("~/.local/share/powershell_es")
		local cache_path = vim.fn.stdpath("cache")
		local cmd_str = string.format(
			"& '%s/PowerShellEditorServices/Start-EditorServices.ps1' -BundledModulesPath '%s' -LogPath '%s/powershell_es.log' -SessionDetailsPath '%s/powershell_es.session' -FeatureFlags @() -AdditionalModules @() -HostName 'Neovim' -HostProfileId 'Neovim' -HostVersion '1.0.0' -Stdio -LogLevel 'Normal'",
			bundle_path, bundle_path, cache_path, cache_path
		)
		vim.lsp.start({
			name = "powershell_es",
			cmd = { "pwsh", "-NoLogo", "-NoProfile", "-Command", cmd_str },
			root_dir = root_dir,
		})
	end,
})

