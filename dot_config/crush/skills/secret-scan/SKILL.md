---
name: secret-scan
description: Secret scanning — credentials, API keys, tokens, env files, SSH keys, pre-commit audit
---

# Secret Scan

Check every diff for sensitive data before it lands. Default stance: anything secret stays out of the repo.

## 0. Notify the user of what you know — first

- Before scanning anything, tell the user if this session has already exposed secret material to you: credentials, API keys, tokens, proxy passwords, SSH keys, or anything from `.env`/private configs you have read.
- Name each item and its source (conversation, file read, environment variable, config) — do not paste full values into output unless the user asks.
- State what you are about to do with it and the risk it faces (e.g. a commit that would include the value from the user's env).
- Get the user's call — rotate, allow, or scrub — before proceeding with the diff scan.

## 1. Scan the diff surface

- Paths: `.env`, `.env.*`, `*.key`, `*.pem`, `*.p12`/`*.pfx`/`*.jks`, `*credentials*`, `id_rsa*`, `id_ed25519*`, `~/.ssh`, `~/.aws`, proxy-variable files, config samples.
- Content: API keys and tokens, long random strings assigned to variables, `user:pass@` URL embeds, base64 blobs, cloud account IDs or secrets in fixtures, test files with real-looking credentials.

## 2. Flag, don't assume

- Treat anything suspicious as a finding, then verify: is this a real secret, a placeholder, or a test fixture? Confirm before committing either way.

## 3. If a secret is found

- Remove it from tracked files. Do not commit a "redacted" copy containing the real value.
- If it was already pushed, say so explicitly (history retains it; rotation may be needed) — don't silently rewrite history.

## 4. Right place for credentials

- Environment variables + OS credential stores (e.g. Windows Credential Manager, Linux secret managers), or chezmoi-style on-demand prompts. Never a tracked file, never a committed `.env.example` with real values.

## 5. Report

- State what was scanned, what was found (or confirmed clean), and what you did about each finding.