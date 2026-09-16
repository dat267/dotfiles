---
name: craft-skill
description: Write or revise an agent skill so the model selects it correctly and follows it literally — description discipline, imperative body rules, progressive disclosure, and gates that carry runnable commands. Use when writing a new skill, revising a description, or when a skill never fires. User-invoked via /skill:craft-skill, optionally with a skill path or name.
disable-model-invocation: true
---

# Craft Skill

A skill has two readers and one channel. The **description** is all the model sees when it chooses. The **body** is read only after that choice. A vague description means the skill never fires; a soft body means it fires badly.

Keep the body small enough to load cheaply, and put each rule where the reader acts on it.

## 1. The description decides

Treat the description as a **catalog selection object**, not a summary of the workflow.

| Rule | Limit |
|---|---|
| Length | under 1024 characters |
| Voice | third person |
| Content | what it does, then `Use when …` triggers |
| Forbidden | workflow steps, numbered phases, gate prose, `→ verify:` commands |

The trigger words are the contract. Name the situations in the user's own vocabulary: symptoms, file types, phrasings, command names.

```
Bad:  Guides the refactor process: first interview, then explore, then scope, then slice commits…
Good: Plan a refactor as small reviewable commits through a user interview. Use when the user asks
      to plan a refactor, break a change into safe steps, or reduce architectural friction.
```

**A user-invoked skill costs no prompt tokens.** Add `disable-model-invocation: true` when the skill must run only on `/skill:<name>`. The model then never sees it and it cannot fire on its own. Say so in the description, because that text is the only thing a reader has.

## 2. The body is instructions, not prose

Write the body in **agentic Simplified Technical English**.

| Rule | Limit |
|---|---|
| Instruction sentence | 20 words or fewer |
| Voice | imperative, active |
| Directives | MUST, MUST NOT, NEVER, ALWAYS, DO, DO NOT |
| Banned modals | `should`, `might`, `could`, `may`, `consider`, `try`, `generally`, `typically` |

Banned words apply to instructions. Keep them inside quoted output, error text, and code samples.

Prose that hedges wastes the reader's attention and invites interpretation. State the rule, then state the exception.

## 3. Progressive disclosure

`SKILL.md` is the entry point. Load it, and the reader has enough to act.

Split when any of these holds:

- `SKILL.md` exceeds roughly 100 lines of instruction
- the content covers distinct domains
- advanced material is rarely needed

Put the overflow in `REFERENCE.md` beside it, and link it with a relative path. A single file is correct while the whole skill fits; do not split to look organized.

Add a script only for deterministic work (validation, formatting, generation) that the agent would otherwise re-derive on every run.

## 4. Name and location

- One folder per skill, `SKILL.md` inside. pi discovers `~/.pi/agent/skills/` and `.pi/skills/`.
- Name it a **verb-noun pair**: `audit-code`, `validate-fix`, `plan-refactor`. Avoid nouns with a verb bolted on — `code-auditor`, `fix-validator`.
- Lowercase letters, digits, and hyphens; 1–64 characters; no leading, trailing, or repeated hyphens.
- pi does not require the name to match the folder. Keep them equal anyway, unless one folder is shared across several agent tools.

A recognized name beats a compliant one: `grill-me` earns its exception by being unmistakable.

## 5. Gates carry commands

Every quality gate in the skill MUST name a runnable command.

Declaring the work done requires the command and its output. Narration without evidence is rejected. When a gate cannot run, say which one and why.

```bash
# Banned modals in the body (the frontmatter describes, so skip it)
awk '/^---$/{n++; next} n>=2' skills/<name>/SKILL.md \
  | grep -nE '\b(should|might|could|may|consider|try|generally|typically)\b'

# Body length, for the ~100-line budget
awk '/^---$/{n++; next} n>=2' skills/<name>/SKILL.md | wc -l
```

## Review checklist

- [ ] Description under 1024 characters, third person, triggers present, no workflow steps
- [ ] User-invoked skill sets `disable-model-invocation: true` and says so in the description
- [ ] Body imperative, instruction sentences 20 words or fewer, no banned modals outside quoted text
- [ ] `SKILL.md` under ~100 instruction lines, or the overflow moved to `REFERENCE.md`
- [ ] Every gate names a command, and the skill states what evidence means done
- [ ] Name is a verb-noun pair and matches the folder
- [ ] Read the body once, literally: each step is doable without context from outside the skill