---
name: verify-before-done
description: Pre-completion verification — test, lint, cross-platform check, no scaffolding, report
---

# Verify Before Done

Fast completion checklist — a few seconds per task, catches the cheap and common failures. Run this at the end, not as an introduction.

## 1. Prove it runs

- Execute or parse every changed artifact, not just trust it: compile/syntax-check what you touched (e.g. `python3 -m py_compile`, `sh -n`, template render, `--help`, `go vet`), run the project's tests/lint if they exist, or invoke the changed command with safe arguments.
- If you cannot run something (missing tool, no sandbox, side effects), say so explicitly — never claim "works" on inspection alone.

## 2. Respect conventions

- Check the repo's own guidance first (AGENTS.md, README, sibling files) and match its naming, structure, and idioms.
- Match surrounding code style; don't introduce a one-off flavor.

## 3. Environment and cross-platform

- If the change can run on more than one OS or machine type (shell, PowerShell, configs, installers, templates), check: OS guards, path and env differences (e.g. Termux `$PREFIX`, Windows `$env:USERPROFILE`, case-insensitive PATH), command availability, and quoting rules.
- No hardcoded absolute paths or assumptions that a tool exists without a guard or fallback.

## 4. Leave it clean

- Remove temporary files, test scaffolding, debug prints, caches, and dead code you introduced.
- Never commit secrets, env files, or machine-specific credentials.

## 5. Report

- List the files you changed.
- Give one exact command the user can run to verify each meaningful change.
- State what you actually verified versus what you assumed.