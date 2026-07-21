local M = {}

function M:fetch(job)
	local updates, state = {}, {}
	for i, file in ipairs(job.files) do
		state[i] = false
		if file.cha.is_dummy then goto continue end
		updates[file.url] = file.cha.len == 0 and "inode/empty" or "text/plain"
		state[i] = true
		::continue::
	end
	if next(updates) then
		ya.emit("update_mimes", { updates = updates })
	end
	return state
end

return M
