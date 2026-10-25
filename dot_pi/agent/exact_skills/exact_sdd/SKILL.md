---
name: sdd
description: Guide spec-driven development with GitHub Spec-Kit. Write a constitution, then a specification, technical plan, task list, and implementation, for both new and existing projects. User-invoked via /skill:sdd, optionally with a feature or directory scope.
disable-model-invocation: true
---

# Spec-driven development

Specifications are executable artifacts, not documentation written after the
fact. Each phase produces a file the next phase reads, and implementation
follows the task list rather than improvising from a chat summary.

Adapted from SpillwaveSolutions/sdd-skill (MIT), which builds on GitHub
Spec-Kit by Den Delimarsky and John Lam.

## Artifacts

- `.specify/memory/constitution.md`: project principles, non-negotiable.
- `.specify/feature.json`: the active feature directory, written by the CLI.
- `specs/NNN-slug/spec.md`: what and why, with user stories, functional
  requirements (`FR-`), success criteria (`SC-`), and edge cases.
- `specs/NNN-slug/plan.md`: stack, architecture, contracts, milestones.
- `specs/NNN-slug/tasks.md`: ordered, executable tasks with dependencies.
- `specs/NNN-slug/checklist.md` and analysis reports: optional quality gates.

A project created by an older Spec-Kit may keep `.speckit/` with
`features/NNN-slug/specify.md`. Read what exists and stay consistent; do not
migrate layout unless the user asks.

## Choose the workflow

- New project: read [references/greenfield.md](references/greenfield.md).
- Existing codebase: read [references/brownfield.md](references/brownfield.md).
- Install or repair the CLI: read [references/install.md](references/install.md).

## Working with Pi

Spec-Kit ships a Pi integration. Install it at project creation:

```bash
specify init my-project --integration pi
```

For an existing Spec-Kit project, add it with
`specify integration install pi`; `specify integration use pi` makes it the
default. The integration writes prompts under `.pi/prompts/`, invoked with
`/speckit.specify`, `/speckit.plan`, and so on (dotted, not hyphenated).

Confirm the installed prompts before telling the user to run one: read
`.pi/prompts/`, or check `/help` in Pi. If no integration is installed, either
run `specify integration install pi` or drive the phases from this skill and
write the same artifacts by hand. Report which route you are on.

Older Spec-Kit releases used `--ai` and put prompts elsewhere; do not copy a
command from memory when the project's files show a different layout.

## Phase sequence

Greenfield: constitution, specify, plan, tasks, implement.

Brownfield: analyze, initialize, constitution from existing code, choose a
reverse-engineering depth, specify the new feature, integration plan, tasks,
implement.

Optional between specify and plan: clarify ambiguous requirements, analyze
cross-artifact consistency, generate a checklist. Optional before implement:
re-analyze, since tasks may have drifted from the spec.

Each phase ends when its artifact exists on disk and the user has seen a
summary. See the templates below; do not continue on approval you did not get,
unless the user asked to run straight through.

## Rules

- The constitution wins. A conflict is resolved by changing the constitution
  explicitly, never by quietly weakening a principle in a later artifact.
- Write no implementation code before `tasks.md` exists and is accepted.
- Requirements are numbered, testable, and free of stack decisions. Put stack
  choices in `plan.md`.
- Every phase writes files. A specification that exists only in the chat is
  not an artifact and does not count as a phase.
- Keep edits inside `specs/`, `.specify/`, and generated command files until
  implementation starts.
- Existing projects: analyze before specifying, respect established patterns,
  and plan integration rather than a parallel design.
- Never claim a phase completed without reading the written artifact back.
- Commit per phase only when the workspace allows it and the phase is verified;
  otherwise leave the files for the user to review.

## Phase summary

After each phase, report briefly and ask for a decision. Keep it short enough
to read in one screen:

- Decisions: the two or three choices that matter, each with its rationale.
- Written: the exact artifact paths and what they contain.
- Review: the items most likely to be wrong or to need user input.
- Risks: what the next phase will expose, or what is still unresolved.
- Next: one or two options with the condition that favors each.

Skip the summary only when the user asked to run several phases without
interruption, or when re-running a phase produced no artifact change.

## Feature tracking

Track multiple features only when the project has more than one. Stages:
specified (20%), planned (40%), tasked (60%), in progress (80%), complete
(100%). Keep one status line, for example
`001-auth: tasked 60%, next 002-profile (depends on 001)`, and expand to a full
list only when asked. Update the stage from files on disk, not from memory.

Handle natural language requests directly: add a feature, reorder features,
mark one deferred or complete, show dependencies, or check whether a feature is
ready to start. Ask for priority and dependencies before adding one, and
confirm before removing or reordering. Detect circular dependencies and report
them instead of proceeding.

## Sources

- Spec-Kit: https://github.com/github/spec-kit
- Upstream skill: https://github.com/SpillwaveSolutions/sdd-skill
