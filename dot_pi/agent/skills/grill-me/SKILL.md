---
name: grill-me
description: A relentless interview to sharpen a plan, decision, or design into a settled design tree. User-invoked via /skill:grill-me, optionally with the plan as argument.
disable-model-invocation: true
---

Interview the user relentlessly until you reach a shared understanding. Map the subject as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round of answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment, look it up yourself with the tools available (read files, run commands, check the session state) before asking. Don't block on a slow lookup: only the questions downstream of it wait; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

Do not start implementing while the interview is running. The session is done when the frontier is empty — every branch visited, nothing left silently assumed — and the user confirms the shared understanding. Only then hand off: if the outcome is a coding task, follow the **tdd** skill.
