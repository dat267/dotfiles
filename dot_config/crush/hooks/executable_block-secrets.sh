#!/bin/sh
set -eu

# Security boundary: workspace-only access and secret-path blocking.
# Bash: allowlist of non-executing commands only (no sh/python/node/git-exec).
# Portable: uses only POSIX sh, case, grep -E, realpath/readlink fallback (no -P).

workspace="${CRUSH_PROJECT_DIR:-${CRUSH_CWD:-}}"
path="${CRUSH_TOOL_INPUT_FILE_PATH:-}"
cmd="${CRUSH_TOOL_INPUT_COMMAND:-}"

# Read stdin JSON for tools that pass 'path' instead of 'file_path' (ls, glob, grep)
if [ -z "$path" ] && { [ "${CRUSH_TOOL_NAME:-}" = "ls" ] || [ "${CRUSH_TOOL_NAME:-}" = "glob" ] || [ "${CRUSH_TOOL_NAME:-}" = "grep" ]; }; then
  stdin_data=$(cat 2>/dev/null || true)
  if [ -n "$stdin_data" ]; then
    extracted=$(echo "$stdin_data" | grep -oE '"path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/^"path"[[:space:]]*:[[:space:]]*"//; s/"$//')
    [ -n "$extracted" ] && path=$extracted
  fi
fi

# Always allow Crush virtual paths (crush://)
case "$path" in
  crush://*) echo '{"decision": "allow"}'; exit 0 ;;
esac

# Allow edits to Crush own config directory
case "$path" in
  */.config/crush/*) echo '{"decision": "allow"}'; exit 0 ;;
esac

# Resolve a path with realpath if available, else readlink -f, else raw path.
# (GNU readlink -f is not on macOS/BSD; realpath covers Linux/Termux/Git Bash.)
resolve_path() {
  p="$1"
  out=""
  if command -v realpath >/dev/null 2>&1; then out=$(realpath "$p" 2>/dev/null) || true; fi
  if [ -z "$out" ] && command -v readlink >/dev/null 2>&1; then out=$(readlink -f "$p" 2>/dev/null) || true; fi
  [ -n "$out" ] && echo "$out" || echo "$p"
}

# Deny if a single token refers to a known secret file. Token-level matching:
# embedded prose like "config.env.sample" or "my.ssh/notes" is not a hit
# (real secret paths need a leading "/" or "." component boundary).
# ".env.example" is the one allowed env template.
is_secret_token() {
  tok="$1"
  case "$tok" in
    .env.example|*.env.example) return 1 ;;
  esac
  # directory components (.ssh, .gnupg, aws/git credential files)
  case "$tok" in
    .ssh|.ssh/*|*/.ssh|*/.ssh/*) return 0 ;;
    .gnupg|.gnupg/*|*/.gnupg|*/.gnupg/*) return 0 ;;
    */.aws/credentials|*/.config/git/credentials) return 0 ;;
  esac
  # basename matching: .env variants, npmrc, netrc, private keys
  base="${tok##*/}"
  case "$base" in
    .env|.env.*|.npmrc|.netrc|id_rsa|id_ed25519|id_ecdsa|id_dsa) return 0 ;;
  esac
  return 1
}

#── Path-based tools (view, edit, write, multiedit, grep, glob, ls) ─────
if [ -n "$path" ]; then
  # Workspace boundary
  if [ -n "$workspace" ]; then
    rpath=$(resolve_path "$path")
    rws=$(resolve_path "$workspace")
    case "$rpath" in
      "$rws"|"$rws"/*) ;;  # allowed
      /dev/null|/dev/stdin|/dev/stdout|/dev/stderr) ;;  # allowed
      *)
        echo '{"decision": "deny", "reason": "File is outside the workspace directory"}'
        exit 2
        ;;
    esac
  fi

  # Secret path patterns
  if is_secret_token "$path"; then
    echo '{"decision": "deny", "reason": "File is a known secret path"}'
    exit 2
  fi
fi

#── Bash commands ──────────────────────────────────────────────────────
if [ -n "$cmd" ]; then
  # Allowlist of trusted commands (first word of the pipeline)
  first_word=$(echo "$cmd" | sed 's/^[[:space:]]*//' | cut -d' ' -f1 | cut -d'/' -f1)
  first_word=$(echo "$first_word" | tr -d ';|&')

  trusted='^('
  trusted="${trusted}cd|git|ls|pwd|which|echo|printf|readlink|realpath|basename|dirname"
  trusted="${trusted}|touch|mkdir|cp|mv|ln"
  trusted="${trusted}|cat|head|tail|wc|sort|uniq|cut|tr|grep|rg|find|diff"
  trusted="${trusted}|date"
  trusted="${trusted}|chezmoi"
  trusted="${trusted})$"

  if ! echo "$first_word" | grep -qE "$trusted"; then
    echo '{"decision": "deny", "reason": "Command not in trusted whitelist"}'
    exit 2
  fi

  # Block command substitution ($(...), backticks) — the standard obfuscation
  # vector. Exception: the repo's own commit convention uses
  # `git commit -m "$(cat <<'EOF' ...)"`, so $(cat << is allowed.
  if ! echo "$cmd" | grep -qE '\$\(cat[[:space:]]+<<'; then
    if echo "$cmd" | grep -qE '\$\(|`'; then
      echo '{"decision": "deny", "reason": "Command substitution is not allowed"}'
      exit 2
    fi
  fi

  # Unified secret-path scan over command tokens — nothing can read/write a
  # secret file regardless of the command used (cat, grep, diff, cp, mv,
  # redirects, ...)
  for tok in $(printf '%s' "$cmd" | tr ';|&' ' '); do
    [ -n "$tok" ] || continue
    # strip a pair of surrounding quotes so 'cat ".env"' is still caught
    tok=$(printf '%s' "$tok" | sed "s/^['\"]//; s/['\"]$//")
    [ -n "$tok" ] || continue
    if is_secret_token "$tok"; then
      echo '{"decision": "deny", "reason": "Command references a known secret path"}'
      exit 2
    fi
  done

  # Block git exec/file-read escapes: -c override, config/alias writes, and
# diff --no-index. Checks git's own arguments only (next word after git, or
# the diff subcommand), so prose in commit messages can't false-positive.
  if echo "$cmd" | grep -qE "(^|[[:space:]|;&])git[[:space:]]+(-c|config|alias)([[:space:]]|$)" 2>/dev/null; then
    echo '{"decision": "deny", "reason": "git used in a way that can execute code or read arbitrary files"}'
    exit 2
  fi
  if echo "$cmd" | grep -qE "(^|[[:space:]|;&])git[[:space:]]+diff[[:space:]].*--no-index" 2>/dev/null; then
    echo '{"decision": "deny", "reason": "git diff --no-index reads arbitrary files"}'
    exit 2
  fi
  # Block object reads via colon refs (git show HEAD:.env, git cat-file),
  # which can read any file by basename from git history.
  if echo "$cmd" | grep -qE "(^|[[:space:]|;&])git\s+(show|cat-file|log)\s+.*:" 2>/dev/null; then
    echo '{"decision": "deny", "reason": "git object reads can access any file in history"}'
    exit 2
  fi

  # Block find exec/delete vectors (-exec, -execdir, -ok, -delete)
  if echo "$cmd" | grep -qE "(^|[[:space:]|;&])find\s+.*(-exec|-execdir|-ok|-delete)" 2>/dev/null; then
    echo '{"decision": "deny", "reason": "find exec/delete flag can execute code or destroy files"}'
    exit 2
  fi

  # Block chezmoi cat (prints managed file contents, including private_ sources)
  if echo "$cmd" | grep -qE "(^|[[:space:]|;&])chezmoi(\s+.*)?\s+cat(\b|\s|$)" 2>/dev/null; then
    echo '{"decision": "deny", "reason": "chezmoi cat prints managed file contents"}'
    exit 2
  fi
fi

echo '{"decision": "allow"}'