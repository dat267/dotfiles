local M = {}

local function get_selected_files()
	local sel = {}
	for _, f in ipairs(cx.active.current.files) do
		if f.selected then
			sel[#sel + 1] = f
		end
	end
	if #sel == 0 and cx.active.current.hovered then
		sel[1] = cx.active.current.hovered
	end
	return sel
end

function M:job()
	local files = get_selected_files()
	if #files == 0 then
		return ya.notify({ title = "Extract", content = "No files selected", timeout = 3 })
	end

	for _, f in ipairs(files) do
		local path = tostring(f.url)
		local name = tostring(f.url:name())
		local parent = tostring(f.url:parent())

		local dst = parent .. "/" .. name:gsub("%.[^.]+$", "")
		local child = Command("7z"):args({ "x", "-y", path, "-o" .. dst }):stdout(Command.PIPED):stderr(Command.PIPED):spawn()
		if child then
			child:wait()
		end
	end

	ya.notify({ title = "Extract", content = "Done", timeout = 3 })
	ya.mgr_emit("refresh", {})
end

return M
