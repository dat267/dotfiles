#!/usr/bin/env python3
"""Install Go binaries via SSH (private repos) — short form.

    gim.py [repo[@version]]

Resolves to github.com/dat267/<repo>@<version> (default adl@main; full
module paths accepted). GOPRIVATE scopes proxy/sumdb bypass to the
module owner; a git insteadOf rewrite in the subprocess env turns the
https fetch into SSH (agent key auth) so nothing prompts. All plumbing
lives in the subprocess env — no global git config is touched.

GIM_DRYRUN=1 prints the resolved go install line without running it.
"""

import os
import subprocess
import sys

DEFAULT_SPEC = "github.com/dat267/adl"


def resolve_spec(spec):
    """spec -> (module, version, owner)."""
    spec = spec or DEFAULT_SPEC
    if "@" in spec:
        module, version = spec.split("@", 1)
        version = "@" + version
    else:
        module, version = spec, "@main"
    # Shorthand is anything without a host segment (no dot in the first
    # path element): "adl", "adl/tools". Full paths (github.com/...,
    # gitlab.com/...) pass through untouched.
    if "." not in module.split("/", 1)[0]:
        module = "github.com/dat267/" + module
    # GOPRIVATE owner = host + first path segment (covers every repo of
    # the owner: github.com/dat267 matches github.com/dat267/<repo>/...).
    parts = module.split("/")
    owner = "/".join(parts[:2]) if len(parts) >= 2 else "github.com/dat267"
    return module, version, owner


def build_env(owner):
    env = dict(os.environ)
    env["GOPRIVATE"] = owner
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "url.git@github.com:.insteadOf"
    env["GIT_CONFIG_VALUE_0"] = "https://github.com/"
    return env


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    module, version, owner = resolve_spec(argv[0] if argv else None)
    target = module + version
    if os.environ.get("GIM_DRYRUN"):
        print(f"go install {target}  (GOPRIVATE={owner}, ssh fetch)")
        return 0
    return subprocess.run(["go", "install", target], env=build_env(owner)).returncode


if __name__ == "__main__":
    sys.exit(main())