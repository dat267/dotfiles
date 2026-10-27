---
name: doc-maintenance
description: Audit a repo's documentation against the current code and fix drift with minimal edits. The five project files, README.md, AGENTS.md, TODO.md, PROGRESS.md, and DECISIONS.md, come first, then every other doc the repo ships. Invoked explicitly, optionally with a file or scope.
disable-model-invocation: true
---

# Doc Maintenance

Audit the docs against what the code does **now**, and fix drift with minimal edits. No rewrites, no churn.

This is the periodic counterpart to the change-time habit: when a change touches something a doc describes, update it in the same commit. This skill catches what
that habit missed, by comparing the docs to the code as it stands now.

## When to run

- Periodically, or after a run of feature or removal work
- When asked "are the docs up to date / accurate?"
- Before a release, or after a long pause
- After adopting a repo whose docs you do not trust

## 1. Inventory the documents

Start with the five project files, which carry the project's state. Find which exist:

```bash
ls README.md AGENTS.md TODO.md PROGRESS.md DECISIONS.md 2>/dev/null
```

| File | Must be true about |
|---|---|
| `README.md` | install and usage commands, feature list, supported platforms |
| `AGENTS.md` | layout, conventions, build and test commands, policies |
| `TODO.md` | the open work that is actually left, at the right priority |
| `PROGRESS.md` | current state, completed work, blockers, next steps |
| `DECISIONS.md` | choices that still hold, with the alternatives rejected |

Missing files are a finding, not something to create in a doc pass: say which are missing and offer to add them.

Then audit every other documentation file the repo ships. Discover them, do not assume. With Git:

```bash
git ls-files -- '*.md' '*.mdx' '*.rst' '*.txt' '*.adoc' \
  | grep -Ev '(^|/)(node_modules|vendor|third_party|dist|build|\.git|target)/'
```

Without Git, walk the tree and apply the same exclusions:

```bash
find . -path ./.git -prune -o \
  \( -name '*.md' -o -name '*.mdx' -o -name '*.rst' -o -name '*.txt' -o -name '*.adoc' \) -print \
  | grep -Ev '(^|/)(node_modules|vendor|third_party|dist|build|target)/'
```

Sort what you find beyond the five by audience:

| Audience | Typical files | Must be true about |
|---|---|---|
| Users | `docs/`, `doc/`, guides, tutorials, quickstarts, man pages | install/usage commands, feature lists, supported platforms |
| Contributors | `CONTRIBUTING*`, `ARCHITECTURE*`, `DESIGN*`, editor rule dirs | layout, conventions, build/test commands, policies |
| Spec / product | `SPEC*`, `PRODUCT*`, `ROADMAP*`, ADRs | shipped vs unshipped features, accepted and superseded decisions |
| History | `CHANGELOG*`, release notes, migration notes | entries match what shipped, migrations match the code |
| Project state | `TODO.md`, `PROGRESS.md`, `DECISIONS.md` | open work that already shipped, state and blockers, decisions that still hold |

Also in scope: **behaviour-bearing comment headers** in source files, a comment documenting a flag, a quoting rule, a load order, or a file's purpose.

Out of scope: generated docs built from source, vendored or build trees, lockfiles.

State in one line which files you will audit, before editing. The user may redirect.

## 2. Audit each doc against the current code

Read the code the doc describes; never audit from memory or from a list of
commits. For each doc, check:

1. **Missing capabilities** — code ships something the doc never mentions.
2. **Stale claims** — paths, commands, flags, tools, or defaults that no longer
   exist, or "todo"/"planned" text for work that already shipped.
3. **Command accuracy** — documented commands and examples still run. Run the
   cheap ones, and read the flag or option definitions for the rest.
4. **Table and list accuracy** — feature tables, directory maps, option lists,
   supported-platform lists, and counts.
5. **Cross-references** — links, paths, and examples point at things that exist.
6. **Behavioral comments** — header comments that describe a flag, quoting rule,
   load order, or file purpose still match the code they sit in.

Work doc by doc, and state which doc and which claims you are checking before
editing so the user can redirect. Read each doc whole: a stale claim usually
sits a couple of paragraphs away from a missing one.

## 3. Apply minimal edits

- Fix the fact, not the prose.
- Preserve voice, style, and table shape; match surrounding entries.
- No cosmetic churn — no typo fixes, table reformatting, or reordering unless part of a factual fix.
- No new sections. If a feature needs one, report it as a follow-up.
- Keep the top-level README small; it should not churn often.

## 4. Commit when the workspace allows it

If the project uses version control, stage explicit paths only (never a
whole-tree add):

```bash
git add <the doc paths you edited>
git commit -m "docs: <what was fixed>"
```

Match the repo's commit style from the recent log. If its workflow wants a branch
or PR, create the branch, but still stop before pushing. Push is the user's call:
end by handing them the exact push command. When the workspace reserves commits
for the user, or uses a version-control tool you cannot drive, leave the edits in
the tree and say so instead of committing.

## 5. Verify

- Every sentence written must be true of the code as it stands now. If code and
  doc disagree, decide which is wrong: fix the doc, or report the code bug. Do not
  silently change code in a doc pass.
- Re-read the edited region in context before committing.

## Report

- Files audited, and which claims were checked against which code
- Doc edits made (file → what changed)
- Files missing from the five, and follow-ups that need larger doc work
- The push command for the user, when version control is in use

## Boundaries

- Documentation only: never change code, configs, or scripts in a doc pass.
- Never push; hand the user the command.
- Stage explicit paths, never a whole-tree add.
- If a write is blocked (permissions), stop and hand the user the command instead of working around it.
