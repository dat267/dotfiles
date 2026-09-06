#!/usr/bin/env sh
# Install Go binaries via SSH (private repos) — short form.
#
#   gim.sh                  # github.com/dat267/adl@main
#   gim.sh <repo>           # github.com/dat267/<repo>@main
#   gim.sh <repo>@<ver>     # pinned version
#   gim.sh <full/module/@v> # any module path, version optional
#
# Private fetch plumbing: GOPRIVATE makes Go bypass proxy + sumdb for the
# owner's repos; the git insteadOf rewrite turns the https fetch into SSH
# (agent key auth) so nothing prompts for credentials. Scoped to this one
# invocation via env — no global git config is touched.
#
# GIM_DRYRUN=1 prints the resolved go install line without running it.

set -eu

spec="${1:-github.com/dat267/adl}"

case "$spec" in
  */*) module="${spec%%@*}" ;;           # full path given, strip version
  *) module="github.com/dat267/${spec%%@*}" ;;
esac
case "$spec" in
  *@*) version="@${spec##*@}" ;;
  *) version="@main" ;;
esac
case "$module" in
  github.com/*) owner="${module%/*}" ;;
  *) owner="github.com/dat267" ;;
esac

if [ -n "${GIM_DRYRUN:-}" ]; then
  echo "go install $module$version  (GOPRIVATE=$owner, ssh fetch)"
  exit 0
fi

GOPRIVATE="$owner" \
GIT_CONFIG_COUNT=1 \
GIT_CONFIG_KEY_0='url.git@github.com:.insteadOf' \
GIT_CONFIG_VALUE_0='https://github.com/' \
go install "$module$version"