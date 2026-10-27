# Decisions

Entries are undated; `git log` records when each change landed.

## Chezmoi owns deployment; the source tree is authoritative

- Context: one dotfiles repository for Linux, Windows, and Termux, with per-platform differences and some files that must not be overwritten blindly.
- Decision: chezmoi with the `dot_`, `private_`, `executable_`, `modify_`, `run_once_`, and `run_onchange_` attributes and Go templates for platform guards. Edit source files, never deployed ones. The user runs `chezmoi apply` and `sudo` in their own terminal.
- Alternatives rejected: GNU Stow, which cannot express platform guards, templating, or lifecycle hooks; a bare git repository with manual symlinks, which has no state tracking or per-OS logic.
- Consequences: `.chezmoiignore` and `{{ if eq .chezmoi.os ... }}` carry the platform logic, and the agent hands over deploy commands instead of running them.

## Sandboxing is a whole-process launcher, not an in-process extension

- Context: the agent needs a kernel boundary, and an earlier permissions extension only governed the tool calls it could see.
- Decision: `pi_sandbox` and `pier_sandbox` wrap the whole process in bubblewrap, aliased to `pix` and `piex` so bare `pi` and `pier` stay unsandboxed. The root filesystem is read-only, `$XDG_RUNTIME_DIR` becomes a private tmpfs with only the container socket and ssh agent bound back, and host IPC endpoints are masked after the writable binds.
- Alternatives rejected: keeping the in-process extension with modes and a status indicator, because it leaves the process boundary open and depends on the model cooperating; a network namespace, because it would cut the network access the tool needs.
- Consequences: there is no `/permissions` mode any more; rootless podman runs as a client of the user's host service, outside the writable allowlist; bash calls are constrained only when the parent app was started through a launcher.

## Helper scripts are stdlib-only Python under `exact_py`

- Context: installers and probes have to run on Linux, Windows, and Termux straight after bootstrap.
- Decision: `dot_local/scripts/exact_py/` holds Python scripts that import only the standard library, tested with `unittest`, with the directory marked `exact_` so strays are removed on apply.
- Alternatives rejected: third-party dependencies or a shared virtualenv, which add bootstrap time, a supply-chain surface, and a broken path on Termux.
- Consequences: no formatter or linter configuration and no Makefile; a script that needs a dependency cannot live there.

## Windows CI covers only what Linux cannot exercise

- Context: the Windows npm layout and `.cmd` launchers cannot be run on Linux, and a full matrix would duplicate coverage that already passes locally.
- Decision: one workflow, `.github/workflows/windows.yml`, which runs the `exact_py` suite and the Pi installer, renders every template into a throwaway home, and PowerShell-parses the profile and the two Windows run scripts.
- Alternatives rejected: running the whole test suite on both operating systems, which costs runner time without adding signal.
- Consequences: Windows regressions outside those areas are caught late, so a Windows-only path change should be checked against the workflow triggers.

## The Pi goal extension is disabled by exclusion, not deletion

- Context: the goal extension was useful enough to keep but not wanted in every session.
- Decision: append `-extensions/goal/index.ts` last in `dot_pi/agent/modify_settings.json`, so it overrides an earlier inclusion, and leave the extension source and tests in place.
- Alternatives rejected: deleting the extension, or moving it outside the extensions directory, which would lose the tests and make re-enabling a restore from git.
- Consequences: re-enabling is one line, and the settings template stays idempotent with a user's other extension choices.

## Pi's default theme stays `system`; `flat` is an option

- Context: the panel backgrounds read as blocks on a terminal that already has its own background and palette.
- Decision: ship `dot_pi/agent/themes/flat.json`, where all seven panel tokens are the terminal default and foreground roles are ANSI slots, but keep `"theme": "system"` in settings.
- Alternatives rejected: making `flat` the default, because it removes the only visual signals for list selection and for tool error state; hardcoding a One Dark palette, because it breaks on a light terminal.
- Consequences: `/settings` can switch to `flat`, and switching costs those two cues.

## Project documentation is exactly five files

- Context: state was spread across responses, commit messages, and ad hoc notes, and none of it survived a session.
- Decision: `README.md`, `AGENTS.md`, `TODO.md`, `PROGRESS.md`, and `DECISIONS.md`, each owning one kind of fact. A ten-line summary lives in `APPEND_SYSTEM.md` because only `AGENTS.md` is loaded automatically, and structure, templates, and audit steps live in the `project-docs` skill.
- Alternatives rejected: letting each project invent its own document set, which makes the agent guess where a fact belongs; putting the full conventions in the system prompt, which costs context in every session.
- Consequences: one fact per file with links instead of copies, and missing files are reported rather than silently created.

## Doc audits cover every doc, the five first

- Context: a repo can ship guides, contributor docs, and release notes that drift just as the five files do.
- Decision: `doc-maintenance` confirms the five project files first, then discovers and audits every other documentation file, checking each against the code as it stands rather than against commit history.
- Alternatives rejected: auditing only the five, which misses `docs/` and contributor guides; driving the audit from a lookback window of commits, which misses drift older than the window and needs version control to run.
- Consequences: the skill is longer, and the audit cost scales with how much documentation a repo ships.

## Skills stay tool- and version-control-agnostic

- Context: the skills are personal but get reused in repos that do not use Git and in agent tools that do not use Pi's command syntax.
- Decision: descriptions describe function and trigger, not an invocation string; Git steps are conditional with a non-Git fallback; handoffs to another skill are optional and name the fallback.
- Alternatives rejected: assuming Pi plus Git everywhere, which makes a skill unsatisfiable elsewhere and misroutes the model.
- Consequences: instructions are a little longer, because every Git or cross-skill step has to state what to do without it.

## The Nerd Font installer installs Hack only

- Context: the same glyph set has to look right in Windows Terminal and in the Linux terminals.
- Decision: `install_nerd_font.py` fetches only Hack Nerd Font.
- Alternatives rejected: installing every Nerd Font, which multiplies download size and installs variants that are never selected.
- Consequences: adding another font is a code change, not a flag.
