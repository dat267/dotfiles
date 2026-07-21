local M = {}

local function get_selected()
	return ya.sync(function()
		local files = {}
		for _, f in ipairs(cx.active.current.files) do
			if f.selected then
				files[#files + 1] = tostring(f.url)
			end
		end
		if #files == 0 and cx.active.current.hovered then
			files[1] = tostring(cx.active.current.hovered.url)
		end
		return files
	end)()
end

function M:entry()
	local files = get_selected()
	if #files == 0 then
		return ya.notify({ title = "Extract", content = "No files", timeout = 3 })
	end

	for _, path in ipairs(files) do
		local name = path:match("[^/]+$")
		local parent = path:match("^(.+)/[^/]+$") or "."
		local dst = parent .. "/" .. (name:gsub("%.[^.]+$", "") or name)
		local child = Command("7z"):args({ "x", "-y", path, "-o" .. dst }):spawn()
		if child then child:wait() end
	end

	ya.notify({ title = "Extract", content = "Done", timeout = 3 })
	ya.mgr_emit("refresh", {})
end

return M
