require "nvchad.autocmds"

vim.api.nvim_create_autocmd("FileType", {
  pattern = "go",
  callback = function()
    vim.bo.tabstop = 4
    vim.bo.shiftwidth = 4
    vim.bo.softtabstop = 4
    vim.bo.expandtab = false
  end,
})

vim.api.nvim_create_autocmd("VimLeavePre", {
  group = vim.api.nvim_create_augroup("SaveMessagesLogOnExit", { clear = true }),
  callback = function()
    local log_dir = vim.fn.stdpath "config"
    if vim.fn.isdirectory(log_dir) == 0 then
      vim.fn.mkdir(log_dir, "p")
    end
    local log_file = log_dir .. "/messages.log"
    local msgs = vim.fn.execute "messages"
    if msgs and msgs:match "%S" then
      local timestamp = os.date "%Y-%m-%d %H:%M:%S"
      local header = string.format("--- Session exited at %s ---\n", timestamp)
      local f = io.open(log_file, "a")
      if f then
        f:write(header .. msgs .. "\n\n")
        f:close()
      end
    end
  end,
})
