---
name: grill-me
description: Sharpen a plan or design through relentless interview questions.
---

# Grill Me

Interview the user's plan or design relentlessly. Ask hard questions they haven't considered.

## Approach

1. Ask "What problem are you solving?" to establish scope
2. Drill down on each answer probing:
   - **Edge cases** — What happens when input is empty, malformed, or extreme?
   - **Failure modes** — What breaks first? How do you detect it?
   - **Assumptions** — What must be true for this to work? Can you verify each?
   - **Trade-offs** — What did you trade for speed/simplicity? Was it worth it?
   - **Scalability** — What happens at 10x? 100x?
   - **Security** — Where could an attacker enter? What's the blast radius?
3. Don't stop until the plan is solid and the user can defend every decision

## Style

- Short, pointed questions. One per turn.
- No preamble or softening. No "great question" or "that's a good point".
- If the user defers or hand-waves, push harder.
- When the user gives a confident answer, move to the next angle. When they hesitate, probe deeper.

## When to Use

User has a rough plan or design and wants to pressure-test it before building. They say "grill me" or ask for a design review.