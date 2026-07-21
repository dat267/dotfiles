local M = {}

local function get_selected_files()
	local files = {}
	for _, f in ipairs(cx.active.current.files) do
		if f.selected then files[#files + 1] = { url = tostring(f.url), name = tostring(f.url:name()), parent = tostring(f.url:parent()) } end
	end
	if #files == 0 and cx.active.current.hovered then
		local h = cx.active.current.hovered
		files[1] = { url = tostring(h.url), name = tostring(h.url:name()), parent = tostring(h.url:parent()) }
	end
	return files
end

local sync_selected = ya.sync(get_selected_files)

function M:entry()
	local files = sync_selected()
	if #files == 0 then return ya.notify({ title = "Transcode", content = "No files", timeout = 3 }) end

	local fmt = ya.input({ position = "center", title = "Target extension (e.g. mp4, mp3, mkv, wav):", default = "mp4" })
	if not fmt or (fmt[1].text or "") == "" then return end
	local ext = fmt[1].text:lower()

	for _, f in ipairs(files) do
		local base = f.name:gsub("%.[^.]+$", "")
		local out = f.parent .. "/" .. base .. "." .. ext
		local child = Command("ffmpeg"):args({ "-i", f.url, "-y", out }):spawn()
		ya.notify({ title = "Transcode", content = "Transcoding " .. base .. "...", timeout = 5 })
		if child then child:wait() end
	end
	ya.notify({ title = "Transcode", content = "Done — " .. #files .. " file(s)", timeout = 5 })
	ya.mgr_emit("refresh", {})
end

return M
