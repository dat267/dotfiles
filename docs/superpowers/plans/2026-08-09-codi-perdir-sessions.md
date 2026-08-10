# codi.py Per-Directory Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each host project directory its own opencode session by mounting it at a deterministic per-directory container path, so opencode's native session-per-project keys them separately.

**Architecture:** Add a pure `workspace_path(project_dir)` (sha256-based), mount `{project_dir}:{workspace_path}`, set the container default workdir to `/home/opencode` (exists in the image) and pass `-w {workspace_path}` on the exec commands that need the project dir. Sandbox config and mount matching are parametrized to the workspace path and a new mount-version label. No directory walk-up.

**Tech Stack:** Python 3 stdlib (`hashlib`, `json`, `argparse`, `subprocess`), podman CLI.

## Global Constraints

- No walk-up project-root detection — `resolve_project_dir` stays cwd-or-`--dir`.
- Keep `--continue` flag semantics (now correctly per-directory).
- `/home/opencode` (exists in the image via `useradd`) is the container default workdir; the project dir is entered via `podman exec -w {workspace_path}` so `-w` never references a dir that doesn't exist yet at `podman create` time.
- Tests run headless with python3 (no podman in this environment): pure-function unit tests + `py_compile`.

---

### Task 1: Pure helpers (workspace path, mount, sandbox config, create command)

**Files:**
- Modify: `/workspace/dot_local/scripts/py/executable_codi.py`
- Test: `/tmp/opencode/test_codi.py`

**Interfaces:**
- Produces (used by Task 2):
  - `MOUNT_VERSION = "2"`, `MOUNT_VERSION_LABEL = "codi.mount_version"`
  - `workspace_path(project_dir: str) -> str` → `/home/opencode/projects/<sha256(project_dir)[:16]>`
  - `mount_specs(project_dir: str, workspace: str) -> list[str]` → `[f"{project_dir}:{workspace}"]`
  - `sandbox_config(workspace: str) -> str` → opencode config JSON with the workspace path (and `/home/opencode/**`) allowed, `*` denied
  - `create_container_cmd(project_dir, no_network, workspace, image) -> list[str]` → the podman create argv (`-w /home/opencode`, per-dir `-v`, mount-version label)

- [ ] **Step 1: Write the failing test**

Create `/tmp/opencode/test_codi.py`:

```python
import json
import re
import sys

sys.path.insert(0, "/workspace/dot_local/scripts/py")
import executable_codi as codi

# workspace_path: deterministic, distinct, correct scheme
a = codi.workspace_path("/home/user/repo-a")
b = codi.workspace_path("/home/user/repo-b")
assert a == codi.workspace_path("/home/user/repo-a"), "deterministic"
assert a != b, "distinct per directory"
assert re.fullmatch(r"/home/opencode/projects/[0-9a-f]{16}", a), "scheme: " + a

# mount_specs
assert codi.mount_specs("/home/user/repo-a", a) == [f"/home/user/repo-a:{a}"]

# sandbox_config allows the workspace path
cfg = json.loads(codi.sandbox_config(a))
ext = cfg["permission"]["external_directory"]
assert ext.get(a) == "allow", "workspace path allowed"
assert ext.get(a + "/**") == "allow"
assert ext.get("/home/opencode/**") == "allow"
assert ext.get("*") == "deny"

# mount version constants
assert codi.MOUNT_VERSION == "2"
assert codi.MOUNT_VERSION_LABEL == "codi.mount_version"

# create_container_cmd: default workdir /home/opencode, per-dir mount, version label
cmd = codi.create_container_cmd("/home/user/repo-a", False, a, codi.IMAGE_NAME)
assert "-w" in cmd and cmd[cmd.index("-w") + 1] == "/home/opencode", cmd
assert f"{codi.PROJECT_DIR_LABEL}=/home/user/repo-a" in cmd
assert f"{codi.MOUNT_VERSION_LABEL}=2" in cmd
assert f"/home/user/repo-a:{a}" in cmd
assert codi.IMAGE_NAME in cmd

print("test_codi OK")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 /tmp/opencode/test_codi.py
```

Expected: FAIL — `workspace_path`, `create_container_cmd`, `sandbox_config` don't exist yet (AttributeError).

- [ ] **Step 3: Implement the helpers in `executable_codi.py`**

Add `import hashlib` and `import json` to the top imports.

Add near the label constants:

```python
MOUNT_VERSION = "2"
MOUNT_VERSION_LABEL = "codi.mount_version"
```

Replace the `SANDBOX_CONFIG = """..."""` string constant with a function (same rules, workspace parametrized):

```python
def sandbox_config(workspace):
    return json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "model": "opencode/deepseek-v4-flash-free",
        "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"],
        "permission": {
            "external_directory": {
                "/tmp/opencode/**": "allow",
                "/home/opencode": "allow",
                "/home/opencode/**": "allow",
                workspace: "allow",
                workspace + "/**": "allow",
                "*": "deny",
            },
            "read": {"*": "allow"},
            "task": "ask",
            "bash": {
                "*": "allow",
                "sudo *": "allow",
                "rm -rf /": "deny",
                "rm -rf /*": "deny",
                "shutdown*": "deny",
                "reboot*": "deny",
                "poweroff*": "deny",
                "dd *": "deny",
                "mkfs*": "deny",
            },
        },
    }, indent=2)
```

Add after `resolve_project_dir`:

```python
def workspace_path(project_dir):
    digest = hashlib.sha256(project_dir.encode()).hexdigest()[:16]
    return f"/home/opencode/projects/{digest}"
```

Replace `mount_specs(project_dir)`:

```python
def mount_specs(project_dir, workspace):
    """Only the workspace is mounted from the host. Secrets and dotfiles are
    managed inside the container, so nothing sensitive from the host ever
    crosses into the container."""
    return [f"{project_dir}:{workspace}"]
```

Add a pure command builder and use it from `create_container`:

```python
def create_container_cmd(project_dir, no_network, workspace, image):
    cmd = [
        "create",
        "--name", CONTAINER_NAME,
        "-it",
        "--userns=keep-id",
        "-w", "/home/opencode",
        "--security-opt", "label=disable",
        "--label", f"{PROJECT_DIR_LABEL}={project_dir}",
        "--label", f"{NETWORK_LABEL}={'1' if no_network else '0'}",
        "--label", f"{MOUNT_VERSION_LABEL}={MOUNT_VERSION}",
    ]
    if no_network:
        cmd.append("--network=none")
    for spec in mount_specs(project_dir, workspace):
        cmd.append("-v")
        cmd.append(spec)
    cmd.append("-v")
    cmd.append(f"{HOME_VOLUME}:/home/opencode")
    cmd.append(image)
    cmd.append("sh")
    cmd.append("-c")
    cmd.append('trap "exit 0" TERM; while :; do sleep 1; done')
    return cmd


def create_container(project_dir, no_network, image=IMAGE_NAME):
    log("Creating persistent container...", "cyan")
    workspace = workspace_path(project_dir)
    cmd = create_container_cmd(project_dir, no_network, workspace, image)
    result = podman(*cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
    log(f"Container {CONTAINER_NAME} created.", "green")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 /tmp/opencode/test_codi.py
```

Expected: prints `test_codi OK`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add dot_local/scripts/py/executable_codi.py
git commit -m "feat(codi): per-directory workspace path helpers"
```

---

### Task 2: Wire the workspace path through the container lifecycle

**Files:**
- Modify: `/workspace/dot_local/scripts/py/executable_codi.py`
- Test: `/tmp/opencode/test_codi.py` (extend) + `py_compile`

**Interfaces:**
- Consumes: Task 1 helpers (`workspace_path`, `mount_specs`, `sandbox_config`, `create_container_cmd`, `MOUNT_VERSION`, `MOUNT_VERSION_LABEL`).
- Produces: `get_container_mount_version(name)`, `container_mounts_match` including the mount version, `write_sandbox_config(workspace)`, `bootstrap_if_needed(workspace)`, `run_container(..., workspace)` running opencode/shells with `-w {workspace}`, `main()` threading `workspace`.

- [ ] **Step 1: Extend the test**

Append to `/tmp/opencode/test_codi.py`:

```python
# create_container_cmd with network disabled
cmd2 = codi.create_container_cmd("/x", True, codi.workspace_path("/x"), codi.IMAGE_NAME)
assert "--network=none" in cmd2
assert f"{codi.NETWORK_LABEL}=1" in cmd2
```

- [ ] **Step 2: Modify `container_mounts_match` and add the version getter**

```python
def get_container_mount_version(name):
    result = podman(
        "inspect", name, "--format", "{{index .Config.Labels \"" + MOUNT_VERSION_LABEL + "\"}}",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def container_mounts_match(project_dir, no_network):
    """Recreate is needed when the frozen mount, network setting, or mount
    scheme version drifted."""
    if get_container_project_dir(CONTAINER_NAME) != project_dir:
        return False
    if get_container_network(CONTAINER_NAME) != ("1" if no_network else "0"):
        return False
    if get_container_mount_version(CONTAINER_NAME) != MOUNT_VERSION:
        return False
    return True
```

- [ ] **Step 3: Update `write_sandbox_config` and `bootstrap_if_needed`**

```python
def write_sandbox_config(workspace):
    """Write the permissive sandbox opencode config into the container's home
    volume, overriding the repo's restrictive one after chezmoi applies."""
    ensure_container_running()
    podman(
        "exec", "-i", "-u", "opencode", CONTAINER_NAME,
        "sh", "-c", "mkdir -p ~/.config/opencode && cat > ~/.config/opencode/opencode.json",
        input=sandbox_config(workspace),
    )
```

`bootstrap_if_needed(workspace)`: change the trailing call to
`write_sandbox_config(workspace)`.

- [ ] **Step 4: Update `run_container` to enter the workspace**

```python
def run_container(continue_conversation, root_shell=False, shell=False, workspace=None):
    """Start the container if stopped, then exec opencode, a shell (as the
    opencode user), or a root shell inside; stop it afterwards."""
    ensure_container_running()

    exec_ws = ["-w", workspace] if workspace else []

    if root_shell:
        log("Starting root shell (install system tools; changes persist)...", "cyan")
        try:
            subprocess.run(["podman", "exec", "-it", *exec_ws, "-u", "root", CONTAINER_NAME, "bash"])
        except KeyboardInterrupt:
            pass
        log("Stopping container (state preserved)...", "cyan")
        stop_container()
        return

    if shell:
        log("Starting shell in the container...", "cyan")
        try:
            subprocess.run(["podman", "exec", "-it", *exec_ws, CONTAINER_NAME, "bash"])
        except KeyboardInterrupt:
            pass
        log("Stopping container (state preserved)...", "cyan")
        stop_container()
        return

    inner = ["opencode", "--auto"]
    if continue_conversation:
        inner.append("--continue")
    flag = " --continue" if continue_conversation else ""
    log(f"Running opencode --auto{flag} (Ctrl-D to exit)...", "cyan")
    try:
        subprocess.run(["podman", "exec", "-it", *exec_ws, CONTAINER_NAME, *inner])
    except KeyboardInterrupt:
        pass

    log("Stopping container (state preserved)...", "cyan")
    stop_container()
```

- [ ] **Step 5: Update `main()`**

After `project_dir = resolve_project_dir(...)` and the `Project:` log line, compute and thread the workspace:

```python
    project_dir = resolve_project_dir(os.getcwd(), args.dir)
    workspace = workspace_path(project_dir)
    log(f"Project: {project_dir} -> {workspace}", "cyan")
```

Pass `workspace` to `bootstrap_if_needed(workspace)` and
`run_container(args.continue_conversation, root_shell=args.root, shell=args.shell, workspace=workspace)`.

- [ ] **Step 6: Verify**

```bash
python3 /tmp/opencode/test_codi.py
python3 -m py_compile /workspace/dot_local/scripts/py/executable_codi.py
python3 /workspace/dot_local/scripts/py/executable_codi.py --help
```

Expected: `test_codi OK`; `py_compile` silent; `--help` prints usage (argparse parse OK).

- [ ] **Step 7: Commit**

```bash
git add dot_local/scripts/py/executable_codi.py
git commit -m "feat(codi): mount per-directory workspace path for per-dir sessions"
```

---

### Task 3: Manual verification (user machine, has podman)

- [ ] **Step 1: Upgrade recreate**

```bash
codi --reset
```

Expected: container recreated under the new mount scheme (one-time).

- [ ] **Step 2: Two-directory session separation**

1. `cd /path/to/project-a && codi` — start a conversation, then `--continue` next run.
2. `cd /path/to/project-b && codi` — confirm a fresh session.
3. `cd /path/to/project-a && codi --continue` — confirm it resumes project-a's session, not project-b's.

- [ ] **Step 3: Mount sanity**

```bash
podman inspect opencode-isolate-ctr --format '{{.Mounts}} {{.Config.WorkingDir}}'
```

Expected: a `project_dir:/home/opencode/projects/<hash>` mount, working dir `/home/opencode`.

---

## Self-Review Notes

- **Spec coverage:** workspace_path (T1), mount specs + sandbox config + mount-version recreate (T1/T2), opencode run at the per-dir path (T2), `--continue` kept (T2 run_container), manual verify (T3).
- **Placeholder scan:** all steps concrete.
- **Type consistency:** `workspace_path(str)->str`, `mount_specs(str,str)->list`, `sandbox_config(str)->str`, `create_container_cmd(str,bool,str,str)->list` — identical names/signatures across tasks.
