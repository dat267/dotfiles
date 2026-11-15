#!/usr/bin/env sh
set -e
# -f: without it curl exits 0 on an HTTP error, so a 5xx error page would be
# piped into bash and executed.
curl -fsSL "https://get.sdkman.io" | bash
