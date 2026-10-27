---
name: project-docs
description: Keep a project's five documents straight. README.md says what the project is and how to install and use it, AGENTS.md how to work on it, TODO.md what remains with priorities, PROGRESS.md the current state with completed work, blockers, and next steps, and DECISIONS.md why choices were made and which alternatives were rejected. Use when starting work in a project, deciding where an update belongs, bootstrapping the files, or auditing them for drift.
---

# Project documents

Five files carry a project's state. Each fact has one home.

| File | Owns | Does not own |
|---|---|---|
| `README.md` | What the project is, how to install and use it, supported platforms, entry points | Internal conventions, task lists, history |
| `AGENTS.md` | How to work on it: layout, commands, conventions, constraints, policies | User-facing usage, why a design was chosen |
| `TODO.md` | Every work item not yet done, ordered by priority, with enough context to start | Completed work, current-state narrative |
| `PROGRESS.md` | Where it stands now: completed work, current focus, blockers, and a pointer to the next action | The backlog, or decisions |
| `DECISIONS.md` | Why a choice was made, the alternatives rejected, and what would change the decision | Implementation detail, tasks |

`AGENTS.md` is loaded automatically when Pi runs in the project; the other four must be read.

## TODO or PROGRESS

The two overlap unless they answer different questions. `TODO.md` answers what is left to do; `PROGRESS.md` answers where the work stands.

- `TODO.md` owns every work item that is not done, including blocked ones, which carry what would unblock them.
- `PROGRESS.md` owns no work items. It records completed work, the current focus, and blockers as state, then points at the top of `TODO.md` for what happens next.
- A finished item leaves `TODO.md` and becomes one line under completed work in `PROGRESS.md`.
- New work goes to `TODO.md`, never to the next-action line of `PROGRESS.md`.

## Read before writing

At the start of real work in a project, read the ones that exist. `AGENTS.md` is already in context. Read `PROGRESS.md` and `TODO.md` before planning so the plan continues the work instead of repeating or contradicting it. Read `DECISIONS.md` before changing architecture, a public interface, or a convention, and do not reopen a settled decision without new evidence.

Skip this for a one-line question or a trivial edit.

## Write when work lands

- A completed task: delete it from `TODO.md`, and add one line under completed work in `PROGRESS.md`.
- New work discovered: add it to `TODO.md` at its priority; do not leave it only in the response.
- A blocked item: keep it in `TODO.md` with what would unblock it, and name the blocker in `PROGRESS.md` while it stops work.
- A finished piece of work: refresh the current state and blockers in `PROGRESS.md`, and point its next action at the new top of `TODO.md`.
- A choice with live alternatives: record it in `DECISIONS.md` with the alternatives rejected and the reason.
- A changed install step, command, or convention: update `README.md` or `AGENTS.md` in the same change.

Update in the same piece of work, not in a later cleanup pass.

## Templates

Do not impose these shapes on files that already have their own; extend what exists.

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

`PROGRESS.md`:
```markdown
# Progress
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
- Context: <the situation that forced a choice>
- Decision: <what was chosen>
- Alternatives rejected: <option> because <reason>
- Consequences: <what this commits the project to>
```

## Rules

- One fact, one home. Link between files instead of copying.
- Rewrite rather than append when the file is a snapshot. `PROGRESS.md` states the present, not a full history; completed work stays short.
- Keep `README.md` small. It is the first thing a stranger reads, not the project's memory.
- Record what is true now. A TODO that claims work is open after it shipped is worse than no TODO.
- Do not invent history. If the reason for a past choice is unknown, say it is unrecorded instead of reconstructing a plausible one.
- Do not create these files silently. When a project lacks some, name which are missing and offer to create them; create all five at once only when starting a project or when the user asks for project docs.

## Audit

When asked whether the documents are accurate, check each against the code and the files as they stand, not against commit history:

- `README.md`: do the install and usage commands run, and does the feature list match what ships?
- `AGENTS.md`: do the commands, paths, and conventions match the tree?
- `TODO.md`: is anything listed already done, and is anything known-but-unlisted absent?
- `PROGRESS.md`: does it match the last known state, and are blockers still blockers?
- `DECISIONS.md`: does each recorded decision still hold, and is anything reversed silently?

Fix facts, not prose. Report drift you did not fix, and ask before restructuring a file.

## Report

After maintaining the documents, state which files changed and what changed in each. Keep it to one line per file.
