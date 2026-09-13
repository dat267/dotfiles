## Verify before asserting

Assert from the artifact in front of you, never from memory of how things should be.

- Read the actual contract, file, or schema before writing an expectation against it. How it "should be" is not evidence.
- Probe unfamiliar library or template functions with a one-liner before building on them — signature and argument order included.
- For bulk edits (sed, scripted rewrites) on tracked files: run on a scratch copy, hand-verify the diff, then apply. If a tracked file gets mangled, revert via git and redo with targeted edits.
- Never `git add -A` on a dirty mid-experiment tree — stage explicit paths.
