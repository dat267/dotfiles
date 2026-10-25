# Brownfield workflow

Use when the codebase already exists and SDD has to fit into it. For a new
project, read [greenfield.md](greenfield.md) instead.

## 1. Survey before writing anything

Read enough to describe the system without guessing: entry points, modules and
their responsibilities, data stores and schemas, external interfaces, build and
deploy, test suites, and the conventions the code actually follows. Check
`AGENTS.md`, `README`, and `docs/` first.

Choose a depth and say which one you used:

- Surface, minutes: layout, stack, naming, obvious risks. Enough to start.
- Moderate, default: architecture, interfaces, data model, business logic,
  test coverage, and known debt.
- Deep, expensive: trace critical flows end to end and map failure behavior.
  Only when the upcoming feature touches them.

Record the result where it survives: the response for a quick survey, or
`specs/NNN-slug/analysis.md` when the user wants a durable artifact. Do not
create documentation files unasked.

## 2. Initialize in place

```bash
specify init --here --force --integration pi
```

`--force` overwrites existing files, so check `git status` first and commit or
stash nothing on the user's behalf. If the project already has `.specify/`, skip
this step and inspect the existing feature layout instead.

## 3. Constitution from the code

```text
/speckit.constitution Principles this codebase already follows: <patterns>,
testing, error handling, compatibility.
```

Write down what is true, not what would be nice. Where current practice is
unsafe or inconsistent, record it as a deviation with a plan, not as an
aspiration the next phase will ignore.

Exit when the constitution explains the existing design decisions a newcomer
would question.

## 4. Choose a reverse-engineering strategy

- As-is: no backfill. Use SDD only for new work. Cheapest, and the right default
  for a stable codebase.
- Changed areas: document only the flows the new feature touches, as part of its
  spec and plan. Best balance for most work.
- Broad backfill: reverse-engineer whole subsystems into specs before changing
  anything. Expensive; justify it with a migration, audit, or handover need.

Never backfill the entire system first. It spends the budget before any value
lands and produces specs that drift immediately.

## 5. Specify the new feature

```text
/speckit.specify Add <feature> without breaking <existing behavior>.
```

Include the compatibility surface: existing behavior that must not regress,
current users and callers, data that must survive, and constraints from the
surveyed architecture. Requirements stay behavioral; file names and refactors
belong in the plan.

## 6. Plan the integration

```text
/speckit.plan Integrate with <modules>. Keep <contracts> compatible.
```

The plan must name the seams it uses, the migrations or data backfills, the
rollout or feature-flag order, and the existing tests that cover the touched
area. Prefer changing the existing design over adding a parallel one; when a
parallel design is unavoidable, the plan says how the old path is retired.

Exit when rollback is described and the blast radius is understood.

## 7. Task and implement incrementally

```text
/speckit.tasks
/speckit.implement
```

Order tasks so the system stays working between them: add, migrate, switch,
then remove. Run the existing suite before and after each risky step; a green
existing suite is the main protection against silent regressions.

When reality contradicts the artifacts, amend the spec, plan, or tasks first,
then continue.

## 8. Validate the result

- Reproduction of the original problem, if the feature fixes one.
- Existing tests plus new tests for each success criterion.
- Compatibility checks for the interfaces and data the plan promised to keep.
- A spec-to-code trace: every requirement points at a task and a test.

## Pitfalls

- Reverse-engineering everything before shipping anything.
- Writing a constitution that describes an intended architecture rather than the
  current one, then treating every existing file as a violation.
- Specs that copy the current implementation instead of stating behavior, which
  makes the spec unable to judge a change.
- Big-bang rewrites disguised as "integration plans".
- Leaving the old path and the new path live with no retirement step.
