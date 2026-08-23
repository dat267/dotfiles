---
name: docs-sync
description: Keep documentation in sync with code in the same change. Use when a change alters behavior, configuration, file layout, commands, or conventions that any README, AGENTS.md, table, module list, or comment describes — update those docs in the same commit and list them in your report.
---

# Docs Sync

Documentation drift is a bug. When your change touches something that documentation describes, the docs must move with the code — same commit, no follow-ups.

## 1. Find what documents this change

- List the doc surfaces that mention what you changed: `README.md`, `AGENTS.md`, `docs/`, module/file tables, inline comment headers, example commands in help text.
- Grep for the old behavior's keywords (renamed commands, moved paths, changed flags, removed files) across markdown and comments.

## 2. Update in the same change

- Fix titles, table rows, module lists, conventions lists, and example commands to match the new reality — precisely, not aspirationally.
- Update comments that describe behavior (e.g. a comment header documenting an option's quoting constraints, or a section enumerating a module's load order).
- Match the repo's existing doc style; don't restructure unrelated sections.

## 3. Verify claims

- Every line you write in docs must be true of the code as committed. If the code and the doc disagree, fix the doc — or the code if the code is wrong.

## 4. Scope

- Fix what this change touches, plus any obviously stale reference on those same lines. Do not expand into unrelated doc rewrites.

## 5. Report

- List the doc files updated alongside the code files, so the change is reviewable as one unit.