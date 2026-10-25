# Install and repair Spec-Kit

Spec-Kit needs Python 3.11+, `uv`, and Git only when the Git extension is used.
The CLI is `specify`.

## Persistent install

From PyPI:

```bash
uv tool install specify-cli
```

Pinned to a release (recommended for reproducibility):

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
```

Keep the leading `v` in the tag. Replace an older install with the same tool
that created it, for example `uv tool install --force specify-cli`. Installing
with a different tool can leave the old `specify` first on `PATH`.

## One-time use

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init <project>
```

## Verify

```bash
specify version
```

This proves the command resolves and reports its version. It does not prove
where it was installed from.

## Initialize a project

```bash
specify init <project> --integration pi    # new directory
specify init --here --integration pi       # current directory
specify init --here --force --integration pi
```

`--here` initializes in place. `--force` overwrites existing files (it still
skips symlinks), so confirm the tree is clean or you have a backup before using
it in a populated directory.

Without `--integration`, an interactive terminal prompts for the agent and a
non-interactive run defaults to GitHub Copilot. Pass the flag explicitly in
scripts.

Supported script flavors are Bash, PowerShell, and Python; select with the
script option when the default does not fit the platform.

## Add or change the integration

```bash
specify integration list
specify integration install pi
specify integration use pi
specify integration upgrade pi
```

Installing another integration does not change the default until
`specify integration use` selects it.

## Troubleshooting

- `command not found: uv`: install uv, then rerun the install command.
- `No such option: --integration`: an old `specify` is first on `PATH`.
  Remove or replace that install.
- Prompts missing in Pi: check `.pi/prompts/` exists and the integration is
  installed; otherwise run the phases from the parent skill.
- Wrong feature picked up: set `SPECIFY_FEATURE_DIRECTORY` to the intended
  `specs/NNN-slug` path, or correct `.specify/feature.json`.
- Upgrades of the tool and changes to `specs/` artifacts are separate: a tool
  upgrade does not rewrite the project's specifications.
