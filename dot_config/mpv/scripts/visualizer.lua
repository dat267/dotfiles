local mp = require 'mp'

local function on_video_change(name, val)
    if val == nil or val == false then
        mp.set_property("lavfi-complex", "[aid1]asplit[ao][a]; [a]showcqt=size=1280x720[vo]")
    else
        mp.set_property("lavfi-complex", "")
    end
end

mp.observe_property("vid", "native", on_video_change)
