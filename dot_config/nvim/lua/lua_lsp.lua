vim.api.nvim_create_autocmd("FileType", {
  pattern = "lua",
  callback = function(args)
    local root_markers = { ".luarc.json", ".git" }
    local buf_name = vim.api.nvim_buf_get_name(args.buf)
    local buf_dir = vim.fs.dirname(buf_name)
    local root_dir = vim.fs.root(args.buf, root_markers) or buf_dir

    if root_dir == vim.env.HOME then
      root_dir = buf_dir
    end

    local cmd = "lua-language-server"
    if vim.fn.has("win32") == 1 then
      if vim.fn.executable("lua-language-server.cmd") == 1 then
        cmd = "lua-language-server.cmd"
      elseif vim.fn.executable("lua-language-server.exe") == 1 then
        cmd = "lua-language-server.exe"
      elseif vim.fn.executable("lua-language-server.bat") == 1 then
        cmd = "lua-language-server.bat"
      end
    end

    vim.lsp.start({
      name = "lua-language-server",
      cmd = { cmd },
      root_dir = root_dir,
      settings = {
        Lua = {
          runtime = { version = "LuaJIT" },
          diagnostics = { globals = { "vim" } },
          workspace = {
            checkThirdParty = false,
            library = vim.api.nvim_get_runtime_file("", true),
          },
          telemetry = { enable = false },
        },
      },
    }, { bufnr = args.buf })
  end,
})
