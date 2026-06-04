local wezterm = require 'wezterm'
local config = wezterm.config_builder()
local mux = wezterm.mux

-- Platform Detection
local is_windows = wezterm.target_triple:find("windows") ~= nil
local is_macos = wezterm.target_triple:find("apple") ~= nil or wezterm.target_triple:find("darwin") ~= nil

----------------------------------------------------------------
-- Shell & Directory Configuration
----------------------------------------------------------------
if is_windows then
  -- Default to PowerShell Core (pwsh.exe) with No Logo on Windows
  config.default_prog = { 'pwsh.exe', '-NoLogo' }
  -- Set starting directory to home directory (USERPROFILE)
  config.default_cwd = wezterm.home_dir
end


----------------------------------------------------------------
-- Custom Mapped Keybindings
----------------------------------------------------------------
config.keys = {
  -- Copy to Clipboard: Ctrl+C
  {
    key = 'c',
    mods = 'CTRL',
    action = wezterm.action.CopyTo 'Clipboard',
  },
  -- Paste from Clipboard: Ctrl+V
  {
    key = 'v',
    mods = 'CTRL',
    action = wezterm.action.PasteFrom 'Clipboard',
  },
  -- Duplicate Pane: Alt+Shift+D
  {
    key = 'd',
    mods = 'ALT|SHIFT',
    action = wezterm.action.SplitHorizontal { domain = 'CurrentPaneDomain' },
  },
  -- Spawn New Tab: Ctrl+Shift+T
  {
    key = 't',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.SpawnTab 'CurrentPaneDomain',
  },
  -- Close Tab/Pane: Ctrl+Shift+W
  {
    key = 'w',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.CloseCurrentTab { confirm = true },
  },
  -- Next Tab: Ctrl+Tab
  {
    key = 'Tab',
    mods = 'CTRL',
    action = wezterm.action.ActivateTabRelative(1),
  },
  -- Previous Tab: Ctrl+Shift+Tab
  {
    key = 'Tab',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.ActivateTabRelative(-1),
  },
}

-- Bind Alt+1 through Alt+9 to directly switch to tabs 1 through 9
for i = 1, 9 do
  table.insert(config.keys, {
    key = tostring(i),
    mods = 'ALT',
    action = wezterm.action.ActivateTab(i - 1),
  })
end

----------------------------------------------------------------
-- Migrated Color Schemes
----------------------------------------------------------------
config.color_schemes = {
  ['OneDarkCustom'] = {
    foreground = '#DCDFE4',
    background = '#282C34',
    cursor_bg = '#FFFFFF',
    cursor_fg = '#282C34',
    selection_bg = '#FDF6E3',
    selection_fg = '#282C34',
    ansi = {
      '#000000', -- black
      '#E45649', -- red
      '#50A14F', -- green
      '#C18301', -- yellow
      '#0184BC', -- blue
      '#A626A4', -- purple / magenta
      '#0997B3', -- cyan
      '#C0C0C0', -- white
    },
    brights = {
      '#808080', -- brightBlack
      '#E06C75', -- brightRed
      '#98C379', -- brightGreen
      '#E5C07B', -- brightYellow
      '#61AFEF', -- brightBlue
      '#C678DD', -- brightPurple
      '#56B6C2', -- brightCyan
      '#FFFFFF', -- brightWhite
    },
  },
  ['OneLightCustom'] = {
    foreground = '#383A42',
    background = '#FAFAFA',
    cursor_bg = '#4F525D',
    cursor_fg = '#FAFAFA',
    selection_bg = '#FDF6E3',
    selection_fg = '#383A42',
    ansi = {
      '#FFFFFF', -- black
      '#DF6C75', -- red
      '#98C379', -- green
      '#E4C07A', -- yellow
      '#0184BC', -- blue
      '#C577DD', -- purple / magenta
      '#56B5C1', -- cyan
      '#808080', -- white
    },
    brights = {
      '#C0C0C0', -- brightBlack
      '#E45649', -- brightRed
      '#50A14F', -- brightGreen
      '#C18301', -- brightYellow
      '#61AFEF', -- brightBlue
      '#A626A4', -- brightPurple
      '#0997B3', -- brightCyan
      '#000000', -- brightWhite
    },
  },
}

----------------------------------------------------------------
-- Dynamic Light/Dark Theme Switching
----------------------------------------------------------------
local function get_system_appearance()
  if wezterm.gui then
    return wezterm.gui.get_appearance()
  end
  return 'Dark' -- safe fallback during early script evaluation
end

local function scheme_for_appearance(appearance)
  if appearance and appearance:find('Dark') then
    return 'OneDarkCustom'
  else
    return 'OneLightCustom'
  end
end

-- Set color scheme based on active system theme
local appearance = get_system_appearance()
config.color_scheme = scheme_for_appearance(appearance)

-- Listen to system theme changes in real-time
wezterm.on('window-config-reloaded', function(window, pane)
  local overrides = window:get_config_overrides() or {}
  -- HIGHLY OPTIMIZED: Use window:get_appearance() directly!
  -- This runs 100% in-process and avoids spawning slow, heavy `reg` subprocesses on Windows.
  local win_appearance = window:get_appearance()
  local scheme = scheme_for_appearance(win_appearance)
  if overrides.color_scheme ~= scheme then
    overrides.color_scheme = scheme
    window:set_config_overrides(overrides)
  end
end)

----------------------------------------------------------------
-- Startup Settings
----------------------------------------------------------------
-- Start fully maximized
wezterm.on('gui-startup', function(cmd)
  local tab, pane, window = mux.spawn_window(cmd or {})
  window:gui_window():maximize()
end)

----------------------------------------------------------------
-- Aesthetics & Window Styling
----------------------------------------------------------------
-- Font configuration with Nerd Font and ligatures
config.font = wezterm.font_with_fallback({
  { family = 'FiraCode Nerd Font', weight = 'Medium' },
  { family = 'Fira Code', weight = 'Medium' },
  { family = 'Consolas', weight = 'Regular' },
})
config.font_size = 11.5

-- Glassmorphism / Transparency & Backdrop Optimizations
-- Note: Setting opacity to 1.0 and backdrop to 'Disable' reduces CPU/GPU compositing overhead to 0%.
-- This completely eliminates resizing stutter and scrolling lag on Windows.
config.window_background_opacity = 1.0
config.win32_system_backdrop = 'Disable'

-- If you prefer transparency and have a strong GPU, uncomment the block below:
-- config.window_background_opacity = 0.90
-- if is_windows then
--   config.win32_system_backdrop = 'Mica' -- Mica uses hardware-accelerated static compositor layers
-- elseif is_macos then
--   config.macos_window_background_blur = 20
-- end

-- Keep native OS controls and borders
config.window_decorations = "TITLE | RESIZE"

-- Subtle padding inside terminal pane
config.window_padding = {
  left = 12,
  right = 12,
  top = 12,
  bottom = 12,
}

----------------------------------------------------------------
-- Tab Bar Styling
----------------------------------------------------------------
config.use_fancy_tab_bar = true
config.hide_tab_bar_if_only_one_tab = true

----------------------------------------------------------------
-- Performance & Rendering Optimizations (Windows Focus)
----------------------------------------------------------------
-- Frontend rendering engine:
-- Options: "OpenGL" (recommended stable/fast), "WebGpu" (cutting-edge, fast on dedicated GPUs), "Software" (CPU fallback)
config.front_end = "OpenGL"

-- Limit the scrollback buffer size to save RAM and CPU overhead during searches/scrolls
config.scrollback_lines = 5000

-- Cap framerate to match typical displays without burning CPU cycles
config.max_fps = 60 -- 60 FPS is very CPU-friendly and feels perfectly smooth for text

-- Avoid background threads trying to reload images or animations constantly
config.animation_fps = 1

-- Optimize cursor animation and blink rate to reduce unnecessary screen redrawing cycles
config.cursor_blink_rate = 500
config.cursor_blink_ease_in = "Constant"
config.cursor_blink_ease_out = "Constant"

return config
