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
		return ya.notify({ title = "Compress", content = "No files", timeout = 3 })
	end

	local fmt = ya.input({ title = "Format: (z)ip or (7)z?" })
	if not fmt then return end
	local format = (fmt[1].text or ""):lower()
	if format ~= "z" and format ~= "7" then
		return ya.notify({ title = "Compress", content = "Enter z or 7", timeout = 3 })
	end

	local name = ya.input({ title = "Output filename:" })
	if not name or (name[1].text or "") == "" then return end
	local out = name[1].text .. (format == "z" and ".zip" or ".7z")

	local args = { "a", "-mmt=on", "-mx=5", out }
	if format == "z" then args[#args + 1] = "-tzip" end
	for _, p in ipairs(files) do args[#args + 1] = p end

	local child = Command("7z"):args(args):spawn()
	ya.notify({ title = "Compress", content = "Compressing...", timeout = 5 })
	if child then child:wait() end
	ya.notify({ title = "Compress", content = "Created " .. out, timeout = 5 })
	ya.mgr_emit("refresh", {})
end

return M
