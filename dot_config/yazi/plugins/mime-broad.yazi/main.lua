local IMAGE  = { png = true, jpg = true, jpeg = true, gif = true, webp = true, bmp = true, ico = true, svg = true, avif = true, tiff = true, tif = true, heic = true, heif = true, jxl = true, jp2 = true, hdr = true, exr = true, xcf = true, psd = true, raw = true, cr2 = true, nef = true, arw = true, dng = true, orf = true }
local AUDIO  = { mp3 = true, flac = true, ogg = true, opus = true, m4a = true, wav = true, wma = true, aac = true, aiff = true, ape = true, dsf = true, dsd = true, ac3 = true, dts = true, mid = true, midi = true, amr = true, mpc = true, tak = true, tta = true, wv = true, spx = true, ra = true, ram = true, oga = true, ["3ga"] = true }
local VIDEO  = { mp4 = true, mkv = true, webm = true, avi = true, mov = true, wmv = true, flv = true, mpg = true, mpeg = true, m4v = true, ts = true, m2ts = true, mts = true, vob = true, ogv = true, ogm = true, ["3gp"] = true, ["3g2"] = true, asf = true, rm = true, rmvb = true, divx = true, xvid = true, f4v = true, hevc = true, vp8 = true, vp9 = true, av1 = true, m2v = true }
local ARCHIVE = { zip = true, ["7z"] = true, rar = true, tar = true, gz = true, bz2 = true, bz = true, xz = true, zst = true, lz4 = true, lzma = true, lha = true, lzh = true, cab = true, dmg = true, iso = true, deb = true, rpm = true, msi = true, apk = true, ipa = true, arj = true, cpio = true, br = true, snap = true, appimage = true, flatpak = true }
local DOC    = { pdf = true, epub = true, mobi = true, djvu = true, cbr = true, cbz = true, cb7 = true, cbt = true, doc = true, docx = true, xls = true, xlsx = true, ppt = true, pptx = true, odt = true, ods = true, odp = true }
local FONT   = { ttf = true, otf = true, woff = true, woff2 = true, eot = true }
local EXEC   = { exe = true, dll = true, so = true, dylib = true, bin = true, elf = true, class = true, jar = true, wasm = true }
local DB     = { db = true, sqlite = true, sqlite3 = true, frm = true, mdb = true, accdb = true }
local OTHER  = { swf = true, fla = true, blend = true, glb = true, gltf = true, obj = true, stl = true, fbx = true, ["3ds"] = true, max = true, cur = true, ps = true, eps = true, ai = true, torrent = true }

local NAMED = {
	makefile = "text/plain", dockerfile = "text/plain", gemfile = "text/plain",
	rakefile = "text/ruby", vagrantfile = "text/plain", procfile = "text/plain",
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
