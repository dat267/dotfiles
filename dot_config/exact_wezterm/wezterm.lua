local wezterm = require 'wezterm'
local config = wezterm.config_builder()
local mux = wezterm.mux

local is_windows = wezterm.target_triple:find("windows") ~= nil

if is_windows then
  config.default_prog = { 'pwsh.exe', '-NoLogo' }
  config.default_cwd = wezterm.home_dir
end

config.keys = {
  {
    key = 'c',
    mods = 'CTRL',
    action = wezterm.action.SendString '\x03',
  },
  {
    key = 'c',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.CopyTo 'Clipboard',
  },
  {
    key = 'v',
    mods = 'CTRL',
    action = wezterm.action.PasteFrom 'Clipboard',
  },
  {
    key = 'd',
    mods = 'ALT|SHIFT',
    action = wezterm.action.SplitHorizontal { domain = 'CurrentPaneDomain' },
  },
  {
    key = 't',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.SpawnTab 'CurrentPaneDomain',
  },
  {
    key = 'w',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.CloseCurrentTab { confirm = true },
  },
  {
    key = 'Tab',
    mods = 'CTRL',
    action = wezterm.action.ActivateTabRelative(1),
  },
  {
    key = 'Tab',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.ActivateTabRelative(-1),
  },
}

for i = 1, 9 do
  table.insert(config.keys, {
    key = tostring(i),
    mods = 'ALT',
    action = wezterm.action.ActivateTab(i - 1),
  })
end

config.mouse_bindings = {
  {
    event = { Up = { streak = 1, button = 'Left' } },
    mods = 'NONE',
    action = wezterm.action.CompleteSelection 'ClipboardAndPrimarySelection',
  },
  {
    event = { Up = { streak = 1, button = 'Left' } },
    mods = 'CTRL',
    action = wezterm.action.OpenLinkAtMouseCursor,
  },
  {
    event = { Down = { streak = 1, button = 'Middle' } },
    mods = 'NONE',
    action = wezterm.action.DisableDefaultAssignment,
  },
  {
    event = { Up = { streak = 1, button = 'Middle' } },
    mods = 'NONE',
    action = wezterm.action.DisableDefaultAssignment,
  },
}

wezterm.on('gui-startup', function(cmd)
  local tab, pane, window = mux.spawn_window(cmd or {})
  window:gui_window():maximize()
end)

wezterm.on('format-tab-title', function(tab, tabs, panes, config, hover, max_width)
  local title = tab.active_pane.title
  title = title:gsub("^[^@]+@[^:%s]+:?%s*", "")
  if title == "" then
    title = tab.active_pane.foreground_process_name:gsub(".*/", ""):gsub("%.exe$", "")
  end
  local target_len = 16
  if #title > target_len then
    title = '...' .. title:sub(-(target_len - 7))
  else
    title = title .. string.rep(' ', target_len - #title)
  end
  return '  ' .. title .. '  '
end)

config.font = wezterm.font_with_fallback({
  { family = 'JetBrains Mono', weight = 'Medium' },
  { family = 'Hack',           weight = 'Regular' },
  { family = 'Consolas',       weight = 'Regular' },
  { family = 'monospace' },
})
config.font_size = 11.5

config.window_background_opacity = 1.0
config.win32_system_backdrop = 'Disable'
config.window_decorations = "TITLE | RESIZE"

config.window_padding = {
  left = 12,
  right = 12,
  top = 12,
  bottom = 12,
}

config.use_fancy_tab_bar = false
config.hide_tab_bar_if_only_one_tab = false
config.front_end = "OpenGL"
config.scrollback_lines = 5000
config.max_fps = 60
config.animation_fps = 1
config.cursor_blink_rate = 500
config.cursor_blink_ease_in = "Constant"
config.cursor_blink_ease_out = "Constant"

return config
