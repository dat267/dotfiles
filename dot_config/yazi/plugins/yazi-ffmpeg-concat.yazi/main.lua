local M = {}

local function get_selected_files()
	local files = {}
	for _, f in ipairs(cx.active.current.files) do
		if f.selected then
			files[#files + 1] = { url = tostring(f.url), ext = f.url:ext() or "", parent = tostring(f.url:parent()) }
		end
	end
	return files
end

local sync_selected = ya.sync(get_selected_files)

function M:entry()
	local files = sync_selected()
	if #files < 2 then return ya.notify({ title = "Concat", content = "Select >= 2 files", timeout = 3 }) end

	local is_flac = true
	local ext = files[1].ext
	for _, f in ipairs(files) do if f.ext:lower() ~= "flac" then is_flac = false; break end end

	local parent = files[1].parent
	local parent_name = parent:match("[^/]+$") or "output"
	local default = parent_name .. "_combined." .. (ext ~= "" and ext or "mkv")

	local name = ya.input({ title = "Output filename", default = default })
	if not name or (name[1].text or "") == "" then return end
	local out = name[1].text
	if not out:find("%.") then out = out .. "." .. (ext ~= "" and ext or "mkv") end

	local n = #files
	local cmd = { "ffmpeg" }
	for _, f in ipairs(files) do cmd[#cmd + 1] = "-i"; cmd[#cmd + 1] = f.url end

	if is_flac then
		cmd[#cmd + 1] = "-filter_complex"; cmd[#cmd + 1] = "concat=n=" .. n .. ":v=0:a=1"
		cmd[#cmd + 1] = "-c:a"; cmd[#cmd + 1] = "flac"
	else
		local filter = ""
		for i = 0, n - 1 do filter = filter .. "[" .. i .. ":v][" .. i .. ":a]" end
		filter = filter .. " concat=n=" .. n .. ":v=1:a=1 [v][a]"
		cmd[#cmd + 1] = "-filter_complex"; cmd[#cmd + 1] = filter
		cmd[#cmd + 1] = "-map"; cmd[#cmd + 1] = "[v]"
		cmd[#cmd + 1] = "-map"; cmd[#cmd + 1] = "[a]"
		cmd[#cmd + 1] = "-c:v"; cmd[#cmd + 1] = "libx264"
		cmd[#cmd + 1] = "-c:a"; cmd[#cmd + 1] = "aac"
	end
	cmd[#cmd + 1] = "-y"; cmd[#cmd + 1] = out

	local child = Command("ffmpeg"):args(cmd):spawn()
	ya.notify({ title = "Concat", content = "Concatenating...", timeout = 5 })
	if child then child:wait() end
	ya.notify({ title = "Concat", content = "Created " .. out, timeout = 5 })
	ya.mgr_emit("refresh", {})
end

return M
