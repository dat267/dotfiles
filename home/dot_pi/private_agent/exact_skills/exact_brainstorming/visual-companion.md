# Visual Companion Guide

A browser tab for showing mockups, diagrams, and options during brainstorming.

## When to use it

Decide question by question, not once per session. The test: **would the user understand this better by seeing it than by reading it?**

**Use the browser** when the content itself is visual:

- **UI mockups:** wireframes, layouts, navigation structures, component designs.
- **Architecture diagrams:** system components, data flow, relationship maps.
- **Side-by-side comparisons:** two layouts, two color schemes, two design directions.
- **Design polish:** questions about look and feel, spacing, visual hierarchy.
- **Spatial relationships:** state machines, flowcharts, and entity relationships drawn as diagrams.

**Stay in the terminal** when the content is text or a table:

- **Requirements and scope:** "what does X mean?", "which features are in scope?"
- **Conceptual A/B/C choices:** picking between approaches described in words.
- **Tradeoff lists:** pros and cons, comparison tables.
- **Technical decisions:** API design, data modeling, choosing an architecture.
- **Clarifying questions:** anything answered in words, not by visual preference.

A question *about* a UI topic is not automatically a visual question. "What kind of wizard do you want?" is conceptual, so use the terminal. "Which of these wizard layouts feels right?" is visual, so use the browser.

## How it works

The server watches a directory for HTML files and serves the newest one. You write a file into `screen_dir`; the user sees it in the browser and can click to select options. Their clicks are recorded in `state_dir/events`, which you read on your next turn.

**Fragments or full documents.** If a file starts with `<!DOCTYPE` or `<html`, the server serves it as is, injecting only the helper script. Anything else is wrapped in the frame template, which adds the header, theme CSS, connection status, and the interactive machinery. **Write fragments by default**, and full documents only when you need complete control of the page.

## Starting a session

Start the server only after the user accepts the companion:

```bash
bash scripts/start-server.sh --open

# Prints:
# {"type":"server-started","port":52341,
#  "url":"http://localhost:52341/?key=ab12…",
#  "screen_dir":"/tmp/brainstorm-12345-1706000000/content",
#  "state_dir":"/tmp/brainstorm-12345-1706000000/state"}
```

- Save `screen_dir` and `state_dir` from the output. The session directory is the parent of `screen_dir`. Below, `$STATE_DIR` means the saved `state_dir`.
- The script backgrounds itself; no background flag is needed. Under Git Bash on Windows it runs in the foreground instead, so start it from a persistent terminal there.
- With `--open`, the browser opens on its own when you push the first screen. Share the URL anyway, since headless and remote setups do not auto-open.
- If you lose the startup output, read `$STATE_DIR/server-info`, which holds the same JSON.
- Session files live under the OS temp directory and are deleted when the server stops. Never pass a project directory or write session state into the repository.

**Always share the complete URL.** It carries a session key (`?key=…`), and the server rejects any request without it, so never strip the query string or hand out a bare `http://host:port`. The key keeps stray tabs and other machines on the network from reading the screens or injecting events. After the first load, a cookie remembers the key, so reloads and `/files/*` assets work without it.

**If the URL is unreachable** from the user's browser (common with remote or containerized setups), bind a non-loopback host, and use `--url-host` to set the hostname printed in the URL:

```bash
bash scripts/start-server.sh --host 0.0.0.0 --url-host localhost
```

## The loop

1. **Check that the server is alive, then write a screen.**
   - **Required:** before mentioning the URL or pushing a screen, confirm that `$STATE_DIR/server-info` exists and `$STATE_DIR/server-stopped` does not. If the server has stopped, restart it with `start-server.sh` and share the new URL and port it prints. It exits on its own after 4 hours idle (`--idle-timeout-minutes` changes that).
   - Write each screen to a **new** file in `screen_dir` with your file-creation tool, never with `cat` or a heredoc, which dump noise into the terminal. See [File naming](#file-naming).

2. **Tell the user what to expect, then end your turn.**
   - Repeat the URL every time, not just the first.
   - Summarize what is on screen in a line ("Showing 3 layout options for the homepage").
   - Ask them to answer in the terminal: "Take a look and let me know what you think. Click to select an option if you'd like."

3. **On your next turn**, after they reply in the terminal:
   - Read `$STATE_DIR/events` if it exists. It holds their browser clicks and selections as JSON lines.
   - Combine it with their terminal message. The terminal message is the main feedback; the events add structured detail.

4. **Iterate or advance.** If the feedback changes the current screen, write a new version (`layout-v2.html`). Move to the next question only once the current one is settled.

5. **Clear the screen when you return to the terminal.** When the next step needs no browser (a clarifying question, a tradeoff discussion), push a waiting screen so the user is not left looking at a settled choice:

   ```html
   <!-- filename: waiting.html (or waiting-2.html, etc.) -->
   <div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
     <p class="subtitle">Continuing in terminal...</p>
   </div>
   ```

   When the next visual question comes up, push a new content file as usual.

6. Repeat until done.

## File naming

- Use descriptive names: `platform.html`, `visual-style.html`, `layout.html`.
- Never reuse a filename; every screen is a new file.
- Version iterations with a suffix: `layout-v2.html`, `layout-v3.html`.
- The server shows the file with the newest modification time.

## Writing fragments

Write only what goes inside the page; the frame template supplies the rest.

```html
<h2>Which layout works better?</h2>
<p class="subtitle">Consider readability and visual hierarchy</p>

<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>Single Column</h3>
      <p>Clean, focused reading experience</p>
    </div>
  </div>
  <div class="option" data-choice="b" onclick="toggleSelect(this)">
    <div class="letter">B</div>
    <div class="content">
      <h3>Two Column</h3>
      <p>Sidebar navigation with main content</p>
    </div>
  </div>
</div>
```

No `<html>`, CSS, or `<script>` tags are needed.

## CSS classes

The frame template provides these classes.

### Options (A/B/C choices)

```html
<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>Title</h3>
      <p>Description</p>
    </div>
  </div>
</div>
```

**Multi-select:** add `data-multiselect` to the container and each click toggles an option's selected state.

```html
<div class="options" data-multiselect>
  <!-- same option markup; users can select and deselect several -->
</div>
```

### Cards (visual designs)

```html
<div class="cards">
  <div class="card" data-choice="design1" onclick="toggleSelect(this)">
    <div class="card-image"><!-- mockup content --></div>
    <div class="card-body">
      <h3>Name</h3>
      <p>Description</p>
    </div>
  </div>
</div>
```

### Mockup container

```html
<div class="mockup">
  <div class="mockup-header">Preview: Dashboard Layout</div>
  <div class="mockup-body"><!-- your mockup HTML --></div>
</div>
```

### Split view (side by side)

```html
<div class="split">
  <div class="mockup"><!-- left --></div>
  <div class="mockup"><!-- right --></div>
</div>
```

### Pros and cons

```html
<div class="pros-cons">
  <div class="pros"><h4>Pros</h4><ul><li>Benefit</li></ul></div>
  <div class="cons"><h4>Cons</h4><ul><li>Drawback</li></ul></div>
</div>
```

### Mock elements (wireframe building blocks)

```html
<div class="mock-nav">Logo | Home | About | Contact</div>
<div style="display: flex;">
  <div class="mock-sidebar">Navigation</div>
  <div class="mock-content">Main content area</div>
</div>
<button class="mock-button">Action Button</button>
<input class="mock-input" placeholder="Input field">
<div class="placeholder">Placeholder area</div>
```

### Typography and sections

- `h2`: page title
- `h3`: section heading
- `.subtitle`: secondary text under the title
- `.section`: content block with a bottom margin
- `.label`: small uppercase label

## Browser events

Clicks are appended to `$STATE_DIR/events`, one JSON object per line. The file is cleared whenever you push a new screen.

```jsonl
{"type":"click","choice":"a","text":"Option A - Simple Layout","timestamp":1706000101}
{"type":"click","choice":"c","text":"Option C - Complex Grid","timestamp":1706000108}
{"type":"click","choice":"b","text":"Option B - Hybrid","timestamp":1706000115}
```

The stream shows how the user explored: they may click several options before settling. The last `choice` is usually the final pick, but the pattern of clicks can reveal hesitation or preferences worth asking about.

If the file does not exist, the user did not use the browser; go by their terminal message alone.

## Design tips

- **Match fidelity to the question:** wireframes for layout, polish for polish questions.
- **State the question on each page:** "Which layout feels more professional?", not just "Pick one".
- **Iterate before advancing:** when feedback changes the screen, write a new version.
- **Two to four options** per screen at most.
- **Use real content when it matters.** For a photography portfolio, use real images (Unsplash); placeholder content hides design problems.
- **Keep mockups simple:** focus on layout and structure, not pixel-perfect design.

## Cleaning up

```bash
bash scripts/stop-server.sh "$SESSION_DIR"
```

This stops the server and deletes the session directory.

## Reference

- Frame template (CSS reference): `scripts/frame-template.html`
- Client-side helper: `scripts/helper.js`
