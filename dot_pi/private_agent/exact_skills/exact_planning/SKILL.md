---
name: planning
description: Break work into ordered, verifiable tasks in TODO.md before implementing. Use when requirements exist but the implementation order is not obvious, when a task feels too large or vague to start, or when scope needs to be written down so it survives a session boundary. Not for single-file changes with obvious scope.
---

# Planning

The output of planning is an ordered task list in the workspace `TODO.md`. Nothing else gets created: no plan document, no directory of specs, no tracker.

## When to use

- Requirements exist but the implementation order is not obvious.
- A task feels too large or too vague to start.
- The work spans several files or subsystems and needs scope that survives a session boundary.
- Someone else needs to see the scope before it is built.

Not for single-file changes with obvious scope, or when the requirements already name well-defined steps.

## Step 1: Read before writing

Planning happens in read-only mode. Read the spec and the code that will change, note the conventions already in use, and map what depends on what. Write no code in this step and do not start an implementation task partway through it: the deliverable is the task list.

## Step 2: Order by dependency

Build foundations first. Sketch the graph when it is not obvious:

```
schema
  ├── types and validation
  │     └── handlers
  │           └── client
  └── migrations
```

This fixes the order of the tasks. It is not a set of tasks by itself.

## Step 3: Slice vertically

One task should carry a single piece of behavior from end to end, not one horizontal layer of everything.

Bad, horizontal:

```
Task 1: build the whole schema
Task 2: build every handler
Task 3: build the whole UI
Task 4: connect them
```

Good, vertical:

```
Task 1: a user can create an account
Task 2: a user can log in
Task 3: a user can add an item
Task 4: a user can see their items
```

Each slice leaves the system working and verifiable. Horizontal slices leave everything half-built until the last task, which is where integration surprises hide.

## Step 4: Write each task

Every task in `TODO.md` carries the same fields, short enough to read at a glance:

```markdown
- [ ] Short imperative title
  - Acceptance: the observable condition that proves it works.
  - Verify: the exact command that demonstrates it.
  - Depends on: the task it needs, or nothing.
  - Files: `path/one.ts`, `path/two.ts`.
```

A task with no acceptance criteria is not a task, it is a wish. Prefer criteria you can check by running something; when a criterion is manual, say precisely what to look at.

Verification names the real command for this repository, not "run the tests" and not an invented one. If no such command exists yet, creating it is the first task.

## Step 5: Size each task

| Size | Files | Example |
|---|---|---|
| XS | 1 | Add a validation rule |
| S | 1-2 | Add an endpoint |
| M | 3-5 | One feature slice |
| L | 5-8 | Break it down further |
| XL | 8+ | Too large to start |

Split a task when any of these is true:

- It needs more than one focused session.
- Its acceptance criteria need more than three bullets.
- It touches two unrelated subsystems.
- Its title needs "and".

## Step 6: Place checkpoints

After every two or three tasks, add a checkpoint that establishes the system still works as a whole: the full test suite, a build, or the one user path that matters. Checkpoints catch the case where every task passed alone and the result does not fit together.

Put risky tasks early, while the plan is cheap to change.

## Where tasks live

`TODO.md` in the workspace root, and only there. Do not create `tasks/`, `plan.md`, `docs/plan.md`, a spec directory, or tracker items alongside it.

- If `TODO.md` does not exist, create it with a single heading for this work.
- If it exists, add a section that matches its current shape. Do not restructure or renumber work already in it.
- If it exists and holds unfinished tasks, check whose they are. For the same work being replanned, update in place. For unrelated work, stop and ask before touching it: those unchecked tasks may be the only record of a build in progress somewhere else.
- When the plan changes, edit the existing entries rather than adding a second copy.
- Record a decision, risk, or open question as a line under the task it affects. It does not need its own document, and it must not become a table of speculation.

Keep the list current as the work proceeds: tick tasks off, add the tasks the plan missed, and delete ones that turned out to be wrong. A `TODO.md` that no longer matches reality is worse than none.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "I'll figure it out as I go" | That is how rework happens. Ten minutes of ordering saves hours of untangling. |
| "The tasks are obvious" | Write them anyway. Writing them down surfaces the dependency and the edge case you skipped. |
| "Planning is overhead, I should be coding" | Planning is the work. Coding without it is typing. |
| "I can hold it all in my head" | Context is finite and sessions end. A written list survives both. |
| "This plan file is stale, I'll replace it" | Unchecked tasks may be a build in progress. Ask first. |
| "A separate plan doc is more organized" | It is a second place to forget to update. One list, one source of truth. |

## Red flags

- Starting implementation with no written task list.
- Replacing or reorganizing unfinished work in `TODO.md` without asking.
- Tasks that say "implement the feature" and nothing more.
- No verification step, or one that names a command that does not exist.
- Every task is L or larger.
- No checkpoint anywhere in the plan.
- A task list that grows every session and never shrinks.

## Verification

Before starting the first task, confirm:

- [ ] Every task has acceptance criteria and a verification step.
- [ ] Dependencies are satisfied by the order.
- [ ] No task touches more than about five files.
- [ ] Checkpoints sit between phases.
- [ ] All of it is in `TODO.md`, and nothing else was created.
- [ ] No unfinished work was overwritten without asking.
