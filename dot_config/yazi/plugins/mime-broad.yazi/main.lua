--- Fast MIME categorization: known binary extensions → proper type,
--- everything else → text/plain. No shelling out to file(1).

local IMAGE  = { png = 1, jpg = 1, jpeg = 1, gif = 1, webp = 1, bmp = 1, ico = 1, svg = 1, avif = 1, tiff = 1, tif = 1, heic = 1, heif = 1, jxl = 1, jp2 = 1, hdr = 1, exr = 1, xcf = 1, psd = 1, raw = 1, cr2 = 1, nef = 1, arw = 1, dng = 1, orf = 1 }
local AUDIO  = { mp3 = 1, flac = 1, ogg = 1, opus = 1, m4a = 1, wav = 1, wma = 1, aac = 1, aiff = 1, ape = 1, dsf = 1, dsd = 1, ac3 = 1, dts = 1, mid = 1, midi = 1, amr = 1, mpc = 1, tak = 1, tta = 1, wv = 1, spx = 1, ra = 1, ram = 1, oga = 1, 3ga = 1 }
local VIDEO  = { mp4 = 1, mkv = 1, webm = 1, avi = 1, mov = 1, wmv = 1, flv = 1, mpg = 1, mpeg = 1, m4v = 1, ts = 1, m2ts = 1, mts = 1, vob = 1, ogv = 1, ogm = 1, "3gp" = 1, "3g2" = 1, asf = 1, rm = 1, rmvb = 1, divx = 1, xvid = 1, f4v = 1, hevc = 1, vp8 = 1, vp9 = 1, av1 = 1, m2v = 1 }
local ARCHIVE = { zip = 1, ["7z"] = 1, rar = 1, tar = 1, gz = 1, bz2 = 1, bz = 1, xz = 1, zst = 1, lz4 = 1, lzma = 1, lha = 1, lzh = 1, cab = 1, dmg = 1, iso = 1, deb = 1, rpm = 1, msi = 1, apk = 1, ipa = 1, arj = 1, cpio = 1, br = 1, snap = 1, appimage = 1, flatpak = 1 }
local DOC    = { pdf = 1, epub = 1, mobi = 1, djvu = 1, cbr = 1, cbz = 1, cb7 = 1, cbt = 1, doc = 1, docx = 1, xls = 1, xlsx = 1, ppt = 1, pptx = 1, odt = 1, ods = 1, odp = 1 }
local FONT   = { ttf = 1, otf = 1, woff = 1, woff2 = 1, eot = 1 }
local EXEC   = { exe = 1, dll = 1, so = 1, dylib = 1, bin = 1, elf = 1, class = 1, jar = 1, wasm = 1 }
local DB     = { db = 1, sqlite = 1, sqlite3 = 1, frm = 1, mdb = 1, accdb = 1 }
local OTHER  = { swf = 1, fla = 1, blend = 1, glb = 1, gltf = 1, obj = 1, stl = 1, fbx = 1, "3ds" = 1, max = 1, cur = 1, ps = 1, eps = 1, ai = 1, torrent = 1 }

local NAMED = {
	makefile = "text/plain",
	dockerfile = "text/plain",
	gemfile = "text/plain",
	rakefile = "text/ruby",
	vagrantfile = "text/plain",
	procfile = "text/plain",
}

local ARCHIVE_MIME = {
	["7z"] = "application/x-7z-compressed", gz = "application/gzip", zip = "application/zip",
	tar = "application/x-tar", bz2 = "application/x-bzip2", bz = "application/x-bzip2",
	xz = "application/x-xz", rar = "application/x-rar-compressed", zst = "application/zstd",
	lz4 = "application/x-lz4", lzma = "application/x-lzma", br = "application/x-brotli",
}

local function mime_for(ext)
	if IMAGE[ext]  then return "image/" .. ext end
	if AUDIO[ext]  then return "audio/" .. ext end
	if VIDEO[ext]  then return "video/" .. ext end
	if ARCHIVE_MIME[ext] then return ARCHIVE_MIME[ext] end
	if ARCHIVE[ext] or DOC[ext] or FONT[ext] or EXEC[ext] or DB[ext] or OTHER[ext] then
		return "application/octet-stream"
	end
	return "text/plain"
end

local M = {}

function M:fetch(job)
	local updates, state = {}, {}
	for i, file in ipairs(job.files) do
		state[i] = false
		if file.cha.is_dummy then goto continue end
		if file.cha.len == 0 then
			updates[file.url] = "inode/empty"
			state[i] = true
			goto continue
		end
		local ext = (file.url.ext or ""):lower()
		local name = (file.url.name or ""):lower()
		if NAMED[name] then
			updates[file.url] = NAMED[name]
		else
			updates[file.url] = mime_for(ext)
		end
		state[i] = true
		::continue::
	end
	if next(updates) then
		ya.emit("update_mimes", { updates = updates })
	end
	return state
end

return M
