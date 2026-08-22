---
name: improve-codebase-architecture
description: Analyze and improve the structure, boundaries, and dependencies of a codebase. Use when refactoring for maintainability, reducing coupling, clarifying module responsibilities, or planning architectural improvements.
---

# Improve Codebase Architecture

Use this skill when the goal is to make a codebase easier to understand, change, test, and extend — not just to fix a single bug or add a feature.

## When to use

- Before or during a refactor that crosses module boundaries.
- When coupling, duplication, or unclear responsibilities make changes risky.
- When planning a larger structural change such as extracting a service, library, or module.
- When reviewing a codebase for maintainability and technical debt.

## Steps

1. **Map the current architecture**
   - Identify top-level modules, packages, or components and their responsibilities.
   - Trace the main dependency directions.
   - Note entry points, data flow, and where state lives.

2. **Find structural problems**
   - Circular dependencies.
   - God modules or god objects.
   - Hidden or implicit coupling.
   - Duplicated logic that should be shared.
   - Leaky abstractions and unclear boundaries.
   - Tests that are hard to write because of tight coupling.

3. **Define the target structure**
   - Choose clear responsibilities for each module.
   - Prefer dependency inversion: high-level policy should not depend on low-level details.
   - Make boundaries explicit (interfaces, ports, adapters, public APIs).
   - Keep changes incremental and reversible.

4. **Plan the migration**
   - List the smallest safe steps that improve structure without breaking behavior.
   - Prefer moving code with its tests.
   - Identify risky dependencies and order the work to reduce churn.
   - If needed, add characterization tests before refactoring.

5. **Execute and verify**
   - Make each step independently verifiable.
   - Run tests, type checks, and linters after each move.
   - Update docs and architecture notes when responsibilities change.

## Guardrails

- Do not rewrite working code purely for aesthetic reasons; tie changes to concrete maintainability problems.
- Do not create new abstractions before there is evidence they reduce complexity.
- Keep the public surface as small as reasonable.
- If the current architecture is undocumented, record the improved structure as you go.
