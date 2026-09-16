---
name: organize-workspace
description: Inventory a workspace for disposable artifacts — logs, caches, stale build output, stray drafts — and present a numbered plan for approval before any delete, move, or .gitignore edit. Use when the user asks to clean up, tidy, organize, reclaim space, or asks which files are safe to remove. User-invoked via /skill:organize-workspace, optionally with a path.
disable-model-invocation: true
---

# Organize Workspace

Five steps, always in this order: **inventory → classify → present → confirm → act**.

Deleting is irreversible and cheap to get wrong. The value of this skill is the confirmation step, not the deletion. A tidy workspace matters only while the work stays intact.

## Hard rules

- Stay read-only until the user approves a numbered plan. Inventory uses `du`, `ls`, `find`, and `git status` only.
- NEVER delete or move from a vague glob. Act on named paths, and echo each path back.
- Ask in chat, then stop. Silence is not approval, and "clean up" alone is not approval of specifics.
- NEVER touch `.git/`, `.svn/`, `.hg/`, `node_modules/`, `vendor/`, `venv/`, `.venv/`, `.env*`, `id_rsa*`, `*.pem`.
- NEVER move secrets, keys, or database dumps into a docs or assets tree.
- Do not clean a user's drafts without explicit approval. A draft can be the only copy of an idea.
- When a path lies outside the agent's write scope, DO NOT retry. Give the user the exact command to run.

## 1. Establish scope

Default to the current project root. The user names a path instead — a cache directory outside any repo is valid. Outside a git repo, skip the repository steps.

Record the OS: `.DS_Store` matters on macOS, `*.pid` and `*.log` on Linux.

## 2. Classify the candidates

Group findings into buckets before proposing anything.

| Bucket | Examples | Typical action |
|---|---|---|
| Logs and temp | `*.log`, `logs/`, `tmp/`, `*.pid` | Delete after confirmation |
| Build and cache | `dist/`, `build/`, `out/`, `target/`, `.next/`, `coverage/`, `__pycache__/` | Delete when rebuildable |
| Package caches | `.cache/`, `.turbo/`, `.parcel-cache/` | Offer deletion |
| Stray drafts | root-level `draft*`, `scratch*`, `notes*`, `untitled*` | User chooses: delete, move, or keep |
| Duplicate or dump dirs | `old/`, `backup/`, `copy/`, `*_backup/` | List, then ask |

Prefer `fd` and `rg` when installed; fall back to `find` and `grep`.

```sh
du -sh ./* .[!.]* 2>/dev/null | sort -hr | head -30

find . -type f \( -name '*.log' -o -name '*.pid' \) 2>/dev/null
find . -maxdepth 3 -type d \( -name dist -o -name build -o -name out \
  -o -name target -o -name .next -o -name coverage \) 2>/dev/null
find . -maxdepth 1 -type f -name '*.md' 2>/dev/null

git status -sb
```

Size first, so the user approves with knowledge of what it buys.

## 3. Present the plan

One numbered table, largest first:

| # | Path | Kind | Size | Action |
|---|---|---|---|---|
| 1 | `dist/` | build | 210M | delete |
| 2 | `notes.md` | draft | 4K | keep — user decides |

Then ask a specific question: *"Delete 1–3? Move 4–5? Skip 6?"* Wait for the reply.

## 4. Execute after approval

- Delete named paths only. Prefer a trash-capable tool when installed, else `rm` with paths echoed.
- Create destination directories with `mkdir -p` before moving.
- One batch at a time. Re-list the affected parent directories afterwards.
- Report stderr when a command failed. Do not describe a failure as success.

## 5. Repository hygiene (git repos)

Cleanup exposes untracked noise. Fix the ignore rules as a **separate approvable diff**.

1. Inventory the ignore sources: root `.gitignore`, package-level `.gitignore` files, and `.git/info/exclude`.
2. Map each recurring artifact to an existing rule, and note the gaps.
3. Propose concrete changes only — `+` add, `-` remove, `~` reword — one reason each.
4. Wait for approval of the exact diff before editing the file.
5. Verify with the rule that matched:

```sh
git check-ignore -v path/to/artifact
```

Prefer narrow positive rules. Negation interacts with later rules and parent directories; avoid `!` unless the file already uses it.

A path that is tracked **and** must be ignored needs `git rm -r --cached <path>` as a separate, explicitly approved step. Never rewrite history from this skill.

## Out of scope

- Generated or vendored trees the project manages itself
- Lockfiles, and dependency directories
- Anything the user calls a draft, unless they approve that item by number
- Machine-wide cleanup outside the named scope