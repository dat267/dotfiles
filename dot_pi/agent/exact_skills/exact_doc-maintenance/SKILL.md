---
name: doc-maintenance
description: Own a project's five documents, README.md, AGENTS.md, TODO.md, STATUS.md, and DECISIONS.md. Set them up with the right shape, decide where an update belongs, and audit every doc the repo ships against the current code for drift. Use when starting a project, deciding which file owns a fact, bootstrapping the files, or checking whether docs are accurate.
---

# Doc Maintenance

Two jobs, one convention. Create the five project documents with the right shape when a project starts, then audit the docs against what the code does **now** and fix drift with minimal edits. No rewrites, no churn.

This is the periodic counterpart to the change-time habit: when a change touches something a doc describes, update it in the same commit. This skill catches what that habit missed, by comparing the docs to the code as it stands now.

## When to run

- Starting a project, or a project with none of the five files
- When deciding which file owns a fact
- Periodically, or after a run of feature or removal work
- When asked "are the docs up to date / accurate?"
- Before a release, or after a long pause
- After adopting a repo whose docs you do not trust

## The five project documents

Each fact has one home. Extend the files a project already has; do not impose these shapes on them.

| File | Owns | Does not own |
|---|---|---|
| `README.md` | What the project is, how to install and use it, supported platforms, entry points | Internal conventions, task lists, history |
| `AGENTS.md` | How to work on it: layout, commands, conventions, constraints, policies | User-facing usage, why a design was chosen |
| `TODO.md` | Every work item not yet done, ordered by priority, with enough context to start | Completed work, current-state narrative |
| `STATUS.md` | Where it stands now: completed work, current focus, blockers, and a pointer to the next action | The backlog, or the reasons behind a choice |
| `DECISIONS.md` | Why a choice was made, the alternatives rejected, and what would change the decision | Implementation detail, tasks |

`AGENTS.md` is loaded automatically when Pi runs in the project; the other four must be read.

### TODO or STATUS

The two overlap unless they answer different questions. `TODO.md` answers what is left to do; `STATUS.md` answers where the work stands.

- `TODO.md` owns every work item that is not done, including blocked ones, which carry what would unblock them.
- `STATUS.md` owns no work items. It records completed work, the current focus, and blockers as state, then points at the top of `TODO.md` for what happens next.
- A finished item leaves `TODO.md` and becomes one line under completed work in `STATUS.md`.
- New work goes to `TODO.md`, never to the next-action line of `STATUS.md`.

### STATUS or DECISIONS

`STATUS.md` states effects; `DECISIONS.md` states reasons. A shipped change is one line in the completed list, and the reasoning, if it is worth keeping, is one entry in `DECISIONS.md`.

- A choice that is still open is a `TODO.md` item, never a `DECISIONS.md` entry. An entry records a choice that was made.
- When a decision is replaced, keep the entry and mark it `superseded by <title>` with the reason. Deleting it loses why the project left that path.
- Do not copy rationale into `STATUS.md`, and do not record progress or state in `DECISIONS.md`.

## Creating the documents

This is the setup job, independent of the audit steps below. It defines the shapes those files start with.

Missing files are a finding, not something to add in an audit pass: say which are missing and offer to create them. Create all five at once only for a new project or when the user asks for project docs. Start each from the project's own content, never from lorem ipsum or a guess about what it will become.

`README.md`: what it is, install, first use, supported platforms, license. Keep it small.

`AGENTS.md`: layout, build and test commands, conventions, constraints, policies.

`TODO.md`:
```markdown
# TODO
## Now
- [ ] <task> (<why now>)
## Next
- [ ] <task>
## Later
- [ ] <task>
```

`STATUS.md`:
```markdown
# Status
## Current state
<one paragraph: what works, what does not>
## Completed
- <work done, newest first>
## Blockers
- <blocker, what it stops, and what would unblock it>
## Next action
<the top of TODO.md Now, by name>
```

`DECISIONS.md`:
```markdown
# Decisions
## <short title>
- Date: <YYYY-MM-DD or the repo's convention>
- Status: active, or superseded by <title>
- Context: <the situation that forced a choice>
- Decision: <what was chosen>
- Alternatives rejected: <option> because <reason>
- Consequences: <what this commits the project to>
```

## 1. Inventory the documents

Start with the five project files, which carry the project's state. Find which exist:

```bash
ls README.md AGENTS.md TODO.md STATUS.md DECISIONS.md 2>/dev/null
```

Audit each against its row in the ownership table above. For the three state files that means the work, not the code: open work that already shipped, a next action that no longer matches the top of `TODO.md`, blockers that are gone, decisions that were reversed without a note.

Missing files are a finding, not something to create in an audit pass; see Creating the documents.

Then audit every other documentation file the repo ships. Discover them, do not assume. The commands below also list the five; skip those. With Git:

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

Also in scope: **behavior-bearing comment headers** in source files, a comment documenting a flag, a quoting rule, a load order, or a file's purpose.

Out of scope: generated docs built from source, vendored or build trees, lockfiles.

State in one line which files you will audit, before editing. The user may redirect.

## 2. Audit the remaining docs against the current code

The three state files were checked in step 1. For the docs that describe code, read
that code; never audit from memory or from a list of commits. For each doc, check:

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

- Every sentence written must be true of the code and the project state as they
  stand now. If code and doc disagree, decide which is wrong: fix the doc, or
  report the code bug. Do not silently change code in a doc pass.
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
