local M = {}

local function fmt_path(url)
	return tostring(url)
end

local function parse_ts(s)
	local parts = {}
	for p in s:gmatch("[^:]+") do
		parts[#parts + 1] = tonumber(p)
	end
	if #parts == 3 then
		return parts[1] * 3600 + parts[2] * 60 + parts[3]
	elseif #parts == 2 then
		return parts[1] * 60 + parts[2]
	end
	return parts[1] or 0
end

function M:entry()
	local h = cx.active.current.hovered
	if not h then
		return ya.notify({ title = "Split", content = "No file hovered", timeout = 3 })
	end

	local path = tostring(h.url)
	local base = h.url:name():gsub("%.[^.]+$", "")
	local parent = tostring(h.url:parent())
	local ext = h.url:ext()

	if not ext then
		return ya.notify({ title = "Split", content = "Not a media file", timeout = 3 })
	end

	local result = ya.input({ title = "Timestamps (comma-separated, e.g. 0:30, 1:00):" })
	if not result then
		return
	end

	local inp = result[1].text:gsub("^%s*(.-)%s*$", "%1")
	if inp == "" then
		return
	end

	local points = {}
	for t in inp:gmatch("[^,]+") do
		local trimmed = t:match("^%s*(.-)%s*$")
		if trimmed and trimmed ~= "" then
			points[#points + 1] = parse_ts(trimmed)
		end
	end

	if #points == 0 then
		return ya.notify({ title = "Split", content = "No valid timestamps", timeout = 3 })
	end

	table.sort(points)

	local segments = {}
	local prev = 0
	for i, p in ipairs(points) do
		segments[#segments + 1] = { start = prev, finish = p, idx = i }
		prev = p
	end
	segments[#segments + 1] = { start = prev, finish = nil, idx = #points + 1 }

	ya.notify({ title = "Split", content = "Splitting " .. #segments .. " segments...", timeout = 5 })

	for _, seg in ipairs(segments) do
		local label = string.format("part%02d", seg.idx)
		local out = string.format("%s/%s_%s.%s", parent, base, label, ext or "mkv")
		local args = { "-i", path, "-ss", tostring(seg.start) }
		if seg.finish then
			args[#args + 1] = "-t"
			args[#args + 1] = tostring(seg.finish - seg.start)
		end
		args[#args + 1] = "-c"
		args[#args + 1] = "copy"
		args[#args + 1] = "-y"
		args[#args + 1] = out

		local child = Command("ffmpeg"):args(args):stdout(Command.PIPED):stderr(Command.PIPED):spawn()
		if child then
			child:wait()
		end
	end

	ya.notify({ title = "Split", content = "Done — " .. #segments .. " files created", timeout = 5 })
	ya.mgr_emit("refresh", {})
end

return M
