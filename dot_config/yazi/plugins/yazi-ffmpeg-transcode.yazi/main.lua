local M = {}

function M:job()
	local files = {}
	for _, f in ipairs(cx.active.current.files) do
		if f.selected then
			files[#files + 1] = f
		end
	end
	if #files == 0 and cx.active.current.hovered then
		files[1] = cx.active.current.hovered
	end
	if #files == 0 then
		return ya.notify({ title = "Transcode", content = "No files selected", timeout = 3 })
	end

	local fmt = ya.input({ title = "Target extension (e.g. mp4, mp3, mkv, wav):", default = "mp4" })
	if not fmt or (fmt[1].text or "") == "" then return end
	local ext = fmt[1].text:lower()

	local audio_only = { mp3 = true, flac = true, ogg = true, opus = true, wav = true, aac = true, m4a = true, wma = true }

	for _, f in ipairs(files) do
		local src = tostring(f.url)
		local base = tostring(f.url:name()):gsub("%.[^.]+$", "")
		local parent = tostring(f.url:parent())
		local out = parent .. "/" .. base .. "." .. ext

		local cmd = { "ffmpeg", "-i", src, "-y", out }
		local child = Command("ffmpeg"):args(cmd):stdout(Command.PIPED):stderr(Command.PIPED):spawn()
		ya.notify({ title = "Transcode", content = "Transcoding " .. base .. "...", timeout = 5 })
		if child then child:wait() end
	end

	ya.notify({ title = "Transcode", content = "Done — " .. #files .. " file(s)", timeout = 5 })
	ya.mgr_emit("refresh", {})
end

return M
