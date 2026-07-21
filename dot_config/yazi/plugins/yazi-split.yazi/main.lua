local M = {}

local function get_hovered_file()
	local h = cx.active.current.hovered
	if h then
		return { url = tostring(h.url), name = tostring(h.url:name()), ext = h.url:ext(), parent = tostring(h.url:parent()) }
	end
end

local sync_hovered = ya.sync(get_hovered_file)

local function parse_ts(s)
	local parts = {}
	for p in s:gmatch("[^:]+") do parts[#parts + 1] = tonumber(p) end
	if #parts == 3 then return parts[1] * 3600 + parts[2] * 60 + parts[3] end
	if #parts == 2 then return parts[1] * 60 + parts[2] end
	return parts[1] or 0
end

function M:entry()
	local h = sync_hovered()
	if not h then return ya.notify({ title = "Split", content = "No file", timeout = 3 }) end
	if not h.ext then return ya.notify({ title = "Split", content = "Not media", timeout = 3 }) end

	local result = ya.input({ position = "center", title = "Timestamps (comma-separated, e.g. 0:30, 1:00):" })
	if not result then return end
	local inp = (result[1].text or ""):gsub("^%s*(.-)%s*$", "%1")
	if inp == "" then return end

	local points = {}
	for t in inp:gmatch("[^,]+") do
		local trimmed = t:match("^%s*(.-)%s*$")
		if trimmed and trimmed ~= "" then points[#points + 1] = parse_ts(trimmed) end
	end
	if #points == 0 then return ya.notify({ title = "Split", content = "No timestamps", timeout = 3 }) end

	table.sort(points)
	local segments = {}
	local prev = 0
	for i, p in ipairs(points) do segments[#segments + 1] = { start = prev, finish = p, idx = i }; prev = p end
	segments[#segments + 1] = { start = prev, finish = nil, idx = #points + 1 }

	ya.notify({ title = "Split", content = "Splitting " .. #segments .. " segments...", timeout = 5 })
	for _, seg in ipairs(segments) do
		local label = string.format("part%02d", seg.idx)
		local base = h.name:gsub("%.[^.]+$", "")
		local out = string.format("%s/%s_%s.%s", h.parent, base, label, h.ext or "mkv")
		local args = { "-i", h.url, "-ss", tostring(seg.start) }
		if seg.finish then args[#args + 1] = "-t"; args[#args + 1] = tostring(seg.finish - seg.start) end
		args[#args + 1] = "-c"; args[#args + 1] = "copy"
		args[#args + 1] = "-y"; args[#args + 1] = out
		local child = Command("ffmpeg"):args(args):spawn()
		if child then child:wait() end
	end
	ya.notify({ title = "Split", content = "Done — " .. #segments .. " files", timeout = 5 })
	ya.mgr_emit("refresh", {})
end

return M
