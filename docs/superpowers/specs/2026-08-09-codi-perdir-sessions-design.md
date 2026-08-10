# Design: Per-directory sessions in codi.py

Date: 2026-08-09
Status: Approved

## Goal

Make opencode associate each host project directory with its own session inside
the codi podman container, so `--continue` resumes the correct directory's
conversation. No directory walk-up detection.

## Background / root cause

opencode keys sessions by `project.worktree` — the directory it runs in
(git-root-aware). codi currently mounts every host directory at `/workspace` and
runs opencode there, so all host directories share one `/workspace` project and
sessions bleed together. Both `opencode --dir` and the `opencode <project>`
positional validate that the path exists, so a per-directory project key must be
a real mount path.

## Change (`dot_local/scripts/py/executable_codi.py`)

1. **`workspace_path(project_dir)`** (new pure function):
   `f"/home/opencode/projects/{hashlib.sha256(project_dir.encode()).hexdigest()[:16]}"`
   — deterministic and distinct per host directory (hash avoids sanitization
   collisions and long-path issues).
2. **`mount_specs(project_dir, workspace_path)`** returns
   `[f"{project_dir}:{workspace_path}"]` (was `{project_dir}:/workspace`).
3. **`create_container`** uses `-w {workspace_path}` and the new mount; opencode
   runs there and its native project detection keys sessions per directory.
4. **`sandbox_config(workspace_path)`** — the opencode sandbox JSON is built
   with the actual workspace path in the allowed external directories
   (additionally already covered by `/home/opencode/**`). `write_sandbox_config`
   takes the workspace path and is called from `bootstrap_if_needed`.
5. **Mount-version label** `codi.mount_version=2` stored on the container and
   compared in `container_mounts_match`, so containers created under the old
   `/workspace` scheme are recreated once on upgrade.
6. Host-dir `codi.project_dir` label matching for project-switch recreate stays
   unchanged; `main()` threads `project_dir → workspace_path` into the
   create/bootstrap/run flow.

## Result

- Run codi in dir A → opencode project `/home/opencode/projects/<hashA>`.
- Run codi in dir B → `/home/opencode/projects/<hashB>`.
- `opencode --auto --continue` (via `--continue`) resumes that directory's own
  last session. No state files, no directory walk-up.

## Verification

Unit tests (no podman available in this environment):
1. `workspace_path` is deterministic (same dir → same path) and distinct for
   different dirs; output matches the `/home/opencode/projects/<16 hex>` scheme.
2. `mount_specs` returns `[f"{dir}:{workspace_path}"]`.
3. `sandbox_config(path)` JSON contains the workspace path (and `/home/opencode/**`).
4. `create_container` command includes `-w {workspace_path}`, the new mount, and
   the `codi.mount_version=2` label.

Manual (user machine, has podman):
1. `codi --reset` once (upgrade recreate).
2. Run codi in project A, `--continue`; run codi in project B, `--continue`;
   confirm each resumes its own session.
3. Confirm `podman inspect` shows the per-directory mount path and `-w`.

## Files touched

- `dot_local/scripts/py/executable_codi.py`
