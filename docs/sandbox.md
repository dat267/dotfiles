# Sandbox (pi extension)

Reference for `~/.pi/agent/extensions/sandbox`, source `dot_pi/agent/exact_extensions/exact_sandbox/`. `AGENTS.md` keeps the operational summary; this file holds the mechanics.

## Gate interface

One backend, one gate interface: `gate --ws <workspace> [--allow <path>] -- <cmd>`. `gate --probe` checks the backend once at load.

- **Linux** compiles `gate.c` and applies a Landlock ruleset. This is the only enforcing platform.
- The former Windows low-integrity (Mandatory Integrity Control + `icacls`) and Android/Termux `LD_PRELOAD` backends were removed. Those platforms have no enforcing backend.

With no usable backend (non-Linux, gate compile failure, failed probe) the default is `yolo`, announced with a startup warning, never a gate that runs unconfined.

## Rules for extension code

- Spawn processes via `bash -c ...` or `gate --ws ... -- <cmd>`, never raw `child_process.spawn`. The sandbox's own gate bootstrap (`cc` compile and `--probe`) is the only exception, because no gate exists yet.
- The gate wraps every `bash` call, so `tool_call`/`tool_result` handlers see `event.input.command` as the gate invocation (`... '--' 'bash' '-c' '<cmd>'`), never the user's command. Unwrap before matching on it, or every prefix matcher silently never fires.
- `write`/`edit` targets are checked in-process with symlink resolution.

## Modes

Switch live with `/sandbox <code>`:

| Code | Mode | Meaning |
|---|---|---|
| `RO` | read | bash, write, and edit are removed and blocked |
| `WS` | workspace | kernel-enforced workspace plus allowlist |
| `RW` | yolo | unrestricted |

The two-letter code is pinned to the status line, the only surface that survives `pi -c`: pi drops a notify issued from `session_start` while it restores the transcript. A `WS` request with no backend falls back to `yolo` with a warning.

## Tests

Pure logic lives in `node --test` files beside the sources. The compiled gate (`gate.c`) has no automated coverage; it is verified by hand (compile plus manual run). Do not assume a suite exercises it.
