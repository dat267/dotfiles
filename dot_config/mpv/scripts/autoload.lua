-- This script automatically loads playlist entries before and after the
-- the currently played file. It does so by scanning the directory a file is
-- located in when starting playback. It sorts the directory entries
-- alphabetically, and adds entries before and after the current file to
-- the internal playlist. (It stops if it would add an already existing
-- playlist entry at the same position - this makes it "stable".)
-- Add at most 5000 * 2 files when starting a file (before + after).

--[[
To configure this script use file autoload.conf in directory script-opts (the "script-opts"
directory must be in the mpv configuration directory, typically ~/.config/mpv/).

Example configuration would be:

disabled=no
images=no
videos=yes
audio=yes
additional_image_exts=list,of,ext
additional_video_exts=list,of,ext
additional_audio_exts=list,of,ext
ignore_hidden=yes
same_type=yes
directory_mode=recursive

--]]

MAXENTRIES = 5000
MAXDIRSTACK = 20

local msg = require 'mp.msg'
local options = require 'mp.options'
local utils = require 'mp.utils'

O = {
    disabled = false,
    images = true,
    videos = true,
    audio = true,
    additional_image_exts = "",
    additional_video_exts = "",
    additional_audio_exts = "",
    ignore_hidden = true,
    same_type = false,
    directory_mode = "auto"
}

options.read_options(O, nil, function(list)
    SPLIT_OPTION_EXTS(list.additional_video_exts, list.additional_audio_exts, list.additional_image_exts)
    if list.videos or list.additional_video_exts or
        list.audio or list.additional_audio_exts or
        list.images or list.additional_image_exts then
        CREATE_EXTENSIONS()
    end
    if list.directory_mode then
        VALIDATE_DIRECTORY_MODE()
    end
end)

function Set(t)
    local set = {}
    for _, v in pairs(t) do set[v] = true end
    return set
end

function SetUnion(a, b)
    for k in pairs(b) do a[k] = true end
    return a
end

function Split(s)
    local set = {}
    for v in string.gmatch(s, '([^,]+)') do set[v] = true end
    return set
end

EXTENSIONS_VIDEO = Set {
    '3g2', '3gp', 'avi', 'flv', 'm2ts', 'm4v', 'mj2', 'mkv', 'mov',
    'mp4', 'mpeg', 'mpg', 'ogv', 'rmvb', 'webm', 'wmv', 'y4m'
}

EXTENSIONS_AUDIO = Set {
    'aiff', 'ape', 'au', 'flac', 'm4a', 'mka', 'mp3', 'oga', 'ogg',
    'ogm', 'opus', 'wav', 'wma'
}

EXTENSIONS_IMAGES = Set {
    'avif', 'bmp', 'gif', 'j2k', 'jp2', 'jpeg', 'jpg', 'jxl', 'png',
    'svg', 'tga', 'tif', 'tiff', 'webp'
}

function SPLIT_OPTION_EXTS(video, audio, image)
    if video then O.additional_video_exts = Split(O.additional_video_exts) end
    if audio then O.additional_audio_exts = Split(O.additional_audio_exts) end
    if image then O.additional_image_exts = Split(O.additional_image_exts) end
end

SPLIT_OPTION_EXTS(true, true, true)

function CREATE_EXTENSIONS()
    EXTENSIONS = {}
    if O.videos then SetUnion(SetUnion(EXTENSIONS, EXTENSIONS_VIDEO), O.additional_video_exts) end
    if O.audio then SetUnion(SetUnion(EXTENSIONS, EXTENSIONS_AUDIO), O.additional_audio_exts) end
    if O.images then SetUnion(SetUnion(EXTENSIONS, EXTENSIONS_IMAGES), O.additional_image_exts) end
end

CREATE_EXTENSIONS()

function VALIDATE_DIRECTORY_MODE()
    if O.directory_mode ~= "recursive" and O.directory_mode ~= "lazy" and O.directory_mode ~= "ignore" then
        O.directory_mode = nil
    end
end

VALIDATE_DIRECTORY_MODE()

function ADD_FILES(files)
    local oldcount = mp.get_property_number("playlist-count", 1)
    for i = 1, #files do
        mp.commandv("loadfile", files[i][1], "append")
        mp.commandv("playlist-move", oldcount + i - 1, files[i][2])
    end
end

function GET_EXTENSION(path)
    local match = string.match(path, "%.([^%.]+)$")
    if match == nil then
        return "nomatch"
    else
        return match
    end
end

table.filter = function(t, iter)
    for i = #t, 1, -1 do
        if not iter(t[i]) then
            table.remove(t, i)
        end
    end
end

table.append = function(t1, t2)
    local t1_size = #t1
    for i = 1, #t2 do
        t1[t1_size + i] = t2[i]
    end
end

-- alphanum sorting for humans in Lua
-- http://notebook.kulchenko.com/algorithms/alphanumeric-natural-sorting-for-humans-in-lua

function ALPHANUMSORT(filenames)
    local function padnum(n, d)
        return #d > 0 and ("%03d%s%.12f"):format(#n, n, tonumber(d) / (10 ^ #d))
            or ("%03d%s"):format(#n, n)
    end

    local tuples = {}
    for i, f in ipairs(filenames) do
        tuples[i] = { f:lower():gsub("0*(%d+)%.?(%d*)", padnum), f }
    end
    table.sort(tuples, function(a, b)
        return a[1] == b[1] and #b[2] < #a[2] or a[1] < b[1]
    end)
    for i, tuple in ipairs(tuples) do filenames[i] = tuple[2] end
    return filenames
end

local autoloaded = nil
local added_entries = {}
local autoloaded_dir = nil

function SCAN_DIR(path, current_file, dir_mode, separator, dir_depth, total_files, extensions)
    if dir_depth == MAXDIRSTACK then
        return
    end
    msg.trace("scanning: " .. path)
    local files = utils.readdir(path, "files") or {}
    local dirs = dir_mode ~= "ignore" and utils.readdir(path, "dirs") or {}
    local prefix = path == "." and "" or path
    table.filter(files, function(v)
        -- The current file could be a hidden file, ignoring it doesn't load other
        -- files from the current directory.
        if (O.ignore_hidden and not (prefix .. v == current_file) and string.match(v, "^%.")) then
            return false
        end
        local ext = GET_EXTENSION(v)
        if ext == nil then
            return false
        end
        return extensions[string.lower(ext)]
    end)
    table.filter(dirs, function(d)
        return not ((O.ignore_hidden and string.match(d, "^%.")))
    end)
    ALPHANUMSORT(files)
    ALPHANUMSORT(dirs)

    for i, file in ipairs(files) do
        files[i] = prefix .. file
    end

    table.append(total_files, files)
    if dir_mode == "recursive" then
        for _, dir in ipairs(dirs) do
            SCAN_DIR(prefix .. dir .. separator, current_file, dir_mode,
                separator, dir_depth + 1, total_files, extensions)
        end
    else
        for i, dir in ipairs(dirs) do
            dirs[i] = prefix .. dir
        end
        table.append(total_files, dirs)
    end
end

function FIND_AND_ADD_ENTRIES()
    local path = mp.get_property("path", "")
    local dir, filename = utils.split_path(path)
    msg.trace(("dir: %s, filename: %s"):format(dir, filename))
    if O.disabled then
        msg.debug("stopping: autoload disabled")
        return
    elseif #dir == 0 then
        msg.debug("stopping: not a local path")
        return
    end

    local pl_count = mp.get_property_number("playlist-count", 1)
    THIS_EXT = GET_EXTENSION(filename)
    -- check if this is a manually made playlist
    if (pl_count > 1 and autoloaded == nil) or
        (pl_count == 1 and EXTENSIONS[string.lower(THIS_EXT)] == nil) then
        msg.debug("stopping: manually made playlist")
        return
    else
        if pl_count == 1 then
            autoloaded = true
            autoloaded_dir = dir
            added_entries = {}
        end
    end

    local extensions = {}
    if O.same_type then
        if EXTENSIONS_VIDEO[string.lower(THIS_EXT)] ~= nil then
            extensions = EXTENSIONS_VIDEO
        elseif EXTENSIONS_AUDIO[string.lower(THIS_EXT)] ~= nil then
            extensions = EXTENSIONS_AUDIO
        else
            extensions = EXTENSIONS_IMAGES
        end
    else
        extensions = EXTENSIONS
    end

    local pl = mp.get_property_native("playlist", {})
    local pl_current = mp.get_property_number("playlist-pos-1", 1)
    msg.trace(("playlist-pos-1: %s, playlist: %s"):format(pl_current,
        utils.to_string(pl)))

    local files = {}
    do
        local dir_mode = O.directory_mode or mp.get_property("directory-mode", "lazy")
        local separator = mp.get_property_native("platform") == "windows" and "\\" or "/"
        SCAN_DIR(autoloaded_dir, path, dir_mode, separator, 0, files, extensions)
    end

    if next(files) == nil then
        msg.debug("no other files or directories in directory")
        return
    end

    -- Find the current pl entry (dir+"/"+filename) in the sorted dir list
    local current
    for i = 1, #files do
        if files[i] == path then
            current = i
            break
        end
    end
    if current == nil then
        return
    end
    msg.trace("current file position in files: " .. current)

    -- treat already existing playlist entries, independent of how they got added
    -- as if they got added by autoload
    for _, entry in ipairs(pl) do
        added_entries[entry.filename] = true
    end

    local append = { [-1] = {}, [1] = {} }
    for direction = -1, 1, 2 do -- 2 iterations, with direction = -1 and +1
        for i = 1, MAXENTRIES do
            local pos = current + i * direction
            local file = files[pos]
            if file == nil or file[1] == "." then
                break
            end

            -- skip files that are/were already in the playlist
            if not added_entries[file] then
                if direction == -1 then
                    msg.verbose("Prepending " .. file)
                    table.insert(append[-1], 1, { file, pl_current + i * direction + 1 })
                else
                    msg.verbose("Adding " .. file)
                    if pl_count > 1 then
                        table.insert(append[1], { file, pl_current + i * direction - 1 })
                    else
                        mp.commandv("loadfile", file, "append")
                    end
                end
            end
            added_entries[file] = true
        end
        if pl_count == 1 and direction == -1 and #append[-1] > 0 then
            for i = 1, #append[-1] do
                mp.commandv("loadfile", append[-1][i][1], "append")
            end
            mp.commandv("playlist-move", 0, current)
        end
    end

    if pl_count > 1 then
        ADD_FILES(append[1])
        ADD_FILES(append[-1])
    end
end

mp.register_event("start-file", FIND_AND_ADD_ENTRIES)
