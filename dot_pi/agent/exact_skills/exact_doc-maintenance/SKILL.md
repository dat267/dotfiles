---
name: doc-maintenance
description: Audit a repo's documentation for drift against recent git history and fix it with minimal edits. User-invoked via /skill:doc-maintenance, optionally with a lookback ref or window.
disable-model-invocation: true
---

# Doc Maintenance

Audit the docs against what the code does **now**, and fix drift with minimal edits. No rewrites, no churn.

This is the periodic counterpart to the change-time habit: when a change touches something a doc describes, update it in the same commit. This skill catches what that habit missed.

## When to run

- Periodically, or after a run of feature/removal commits
- When asked "are the docs up to date / accurate?"
- Before a release, or after a long pause

## 1. Find the repo's doc surfaces

Discover, do not assume. List the versioned docs:

```bash
git ls-files -- '*.md' '*.mdx' '*.rst' '*.txt' \
  | grep -Ev '(^|/)(node_modules|vendor|third_party|dist|build|\.git|target)/'
```

Sort what you find by audience:

| Audience | Typical files | Must be true about |
|---|---|---|
| Users | `README*`, `docs/`, `doc/`, guides, quickstarts | install/usage commands, feature lists, supported platforms, directory maps |
| Contributors / agents | `CONTRIBUTING*`, `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE*`, editor rule dirs | layout, conventions, build/test commands, policies |
| Spec / product | `SPEC*`, `PRODUCT*`, `ROADMAP*` | shipped vs unshipped features |

Also in scope: **behaviour-bearing comment headers** in source files — a comment documenting a flag, a quoting rule, a load order, or a file's purpose.

Out of scope unless the repo's own conventions say otherwise: generated docs (API references built from source), `CHANGELOG*` and release notes, skill/prompt files, vendored or build trees, lockfiles. These are low user-facing risk, and auditing them is churn.

State in one line which files you will audit, before editing. The user may redirect.

## 2. Choose the window

Cursor = the last commit that touched any audit target. No state file, and the audit's own doc commit becomes the next cursor:

```bash
DOCS="README.md AGENTS.md"                 # the paths chosen in step 1
LAST=$(git log -1 --format=%H -- $DOCS)
SINCE="${LAST:-$(git log --format=%H --after='60 days ago' --reverse | head -1)}"
git log "$SINCE"..HEAD --oneline --no-merges
```

If the user passed a ref or window (a SHA, `main~20`, `30 days ago`), use it as `$SINCE`. If nothing landed since the cursor, say so and stop.

## 3. Classify changes since the cursor

Infer the repo's commit style instead of assuming one — read `git log -20 --format=%s` and match it. Then classify by content, not by prefix:

| Signal | Category | Audit? |
|---|---|---|
| new capability — new command, flag, module, endpoint, config key, platform | Feature | yes, if user-facing |
| removal — dropped command/flag/tool/module, or a renamed public thing | Removal | yes |
| new directory, new build/test target, changed convention or layout | Structural | maybe |
| internal refactor, test-only, formatting, dependency bumps | Maintenance | no |
| docs-only | Doc | no (already handled) |

Borderline: read the diff. A commit titled "refactor" that adds a public flag or endpoint is a Feature.

## 4. Summarize

```
Since <sha> (<date>):
- FEATURE: <what shipped>
- REMOVAL: <what went away and what replaces it>
- STRUCTURAL: <layout or convention change>
```

## 5. Audit each doc

Read each doc **fully** and check it against the summary:

1. **False negatives** — a shipped capability the doc never mentions.
2. **False positives** — stale paths, removed commands/flags/tools, or "todo"/"planned" claims that already shipped.
3. **Command accuracy** — do the documented commands still run? Run them when cheap.
4. **Table/list accuracy** — feature tables, directory maps, option lists, supported-platform lists.
5. **Cross-references** — links, paths, and examples point at things that exist.

## 6. Apply minimal edits

- Fix the fact, not the prose.
- Preserve voice, style, and table shape; match surrounding entries.
- No cosmetic churn — no typo fixes, table reformatting, or reordering unless part of a factual fix.
- No new sections. If a feature needs one, report it as a follow-up.
- Keep the top-level README small; it should not churn often.

## 7. Commit — never push

Stage explicit paths only (never `git add -A`):

```bash
git add <the doc paths you edited>
git commit -m "docs: <what was fixed>"
```

Match the repo's commit style from step 3. If its workflow wants a branch or PR, create the branch — but still stop before pushing. Push is the user's call: end by handing them the exact `git push` command.

## 8. Verify

- Every sentence written must be true of the code **as committed**. If code and doc disagree, decide which is wrong: fix the doc, or report the code bug. Do not silently change code in a doc pass.
- Re-read the edited region in context before committing.

## Report

- Files audited, and the window scanned (cursor sha/date, commit count)
- Notable changes found, by category
- Doc edits made (file → what changed)
- Follow-ups that need larger doc work (new sections, guides)
- The `git push` command for the user

## Boundaries

- Documentation only: never change code, configs, or scripts in a doc pass.
- Never push — hand the user the command.
- Stage explicit paths; never `git add -A`.
- If a write is blocked (sandbox or permissions), stop and hand the user the command instead of working around it.
