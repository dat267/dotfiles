# Greenfield workflow

Use when nothing exists yet, or a new service or component starts outside the
current codebase. For an existing codebase, read
[brownfield.md](brownfield.md) instead.

## 1. Initialize

```bash
specify init my-project --integration pi
cd my-project
```

The project gets `.specify/` and `.pi/prompts/`. Confirm the prompt names in
`.pi/prompts/` before invoking them.

## 2. Constitution

```text
/speckit.constitution Principles for code quality, testing, UX, and performance.
```

Writes `.specify/memory/constitution.md`. Keep it short and enforceable:
principles that can decide a disagreement, not aspirations. Exit when every
principle has a testable consequence and the user accepts it.

## 3. Specification

```text
/speckit.specify Build <what> so that <who> can <outcome>. Include <constraints>.
```

Writes `specs/NNN-slug/spec.md` and records the active feature in
`.specify/feature.json`. This phase states what and why only: actors, user
stories, numbered functional requirements, measurable success criteria, edge
cases, non-goals. No stack, libraries, or file layout.

Exit when each requirement is testable, each success criterion has a number or
an observable outcome, and the user confirms the scope.

## 4. Clarify (optional)

```text
/speckit.clarify Focus on <ambiguous area>.
```

Use when a requirement could be implemented two ways with materially different
results. Unresolved ambiguity here becomes rework in `plan.md`.

## 5. Plan

```text
/speckit.plan Use <stack>. <Architecture and data decisions.> <Constraints.>
```

Writes `specs/NNN-slug/plan.md`: stack, structure, contracts, data model,
dependencies, risks, and milestone order. It must satisfy the constitution; a
conflict goes back to the constitution, not into a quiet exception.

Exit when the plan names the modules to touch, the interfaces between them, and
the test strategy. Stop here if the user wants to compare stacks first; run the
phase again for the chosen one.

## 6. Tasks

```text
/speckit.tasks
```

Writes `specs/NNN-slug/tasks.md`: ordered, small tasks grouped in phases, each
with its requirement or user story, dependencies, and a checkable outcome.

Exit when every functional requirement maps to at least one task and no task
depends on a decision the plan does not contain.

## 7. Analyze and checklist (optional but cheap)

```text
/speckit.analyze
/speckit.checklist <focus>
```

`analyze` reports cross-artifact gaps, contradictions, and untestable
requirements. `checklist` produces a quality gate for the feature. Fix the
artifacts before implementing; do not carry findings into code.

## 8. Implement

```text
/speckit.implement
```

Work through `tasks.md` in order. Mark tasks as they complete, keep the code
matching the plan, and stop to amend the spec when reality contradicts it:
change `spec.md`, `plan.md`, or `tasks.md`, then continue. Never let the
implementation silently diverge from the artifacts.

Verify with the project gate and the success criteria from `spec.md`. A feature
is complete when those criteria are observed, not when the tasks are checked
off.

## Pitfalls

- Writing requirements after seeing the code, which turns the spec into a
  description of an accident.
- Letting `plan.md` introduce requirements that `spec.md` never stated.
- Task lists that are really file lists: "edit file X" is not a task outcome.
- A constitution with no enforcement path. If nothing can violate a principle,
  it does not belong there.
- Implementing several features in one branch. One feature directory per
  branch keeps the artifacts and the diff aligned.

## Multi-feature projects

Repeat steps 3 to 8 per feature. Track stage from files on disk: specified,
planned, tasked, in progress, complete. Order features by dependency, not by
enthusiasm, and resolve circular dependencies before starting.
