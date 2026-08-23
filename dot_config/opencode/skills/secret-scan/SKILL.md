---
name: secret-scan
description: Pre-commit review for secrets and sensitive data. Use when writing or reviewing any diff that could touch credentials, env files, API keys, SSH keys, proxy credentials, cloud configs, tokens, or machine-local paths — scan, flag, and scrub before finishing, and prefer OS credential stores over tracked files.
---

# Secret Scan

Check every diff for sensitive data before it lands. Default stance: anything secret stays out of the repo.

## 1. Scan the diff surface

- Paths: `.env`, `.env.*`, `*.key`, `*.pem`, `*.p12`/`*.pfx`/`*.jks`, `*credentials*`, `id_rsa*`, `id_ed25519*`, `~/.ssh`, `~/.aws`, proxy-variable files, config samples.
- Content: API keys and tokens, long random strings assigned to variables, `user:pass@` URL embeds, base64 blobs, cloud account IDs or secrets in fixtures, test files with real-looking credentials.

## 2. Flag, don't assume

- Treat anything suspicious as a finding, then verify: is this a real secret, a placeholder, or a test fixture? Confirm before committing either way.

## 3. If a secret is found

- Remove it from tracked files. Do not commit a "redacted" copy containing the real value.
- If it was already pushed, say so explicitly (history retains it; rotation may be needed) — don't silently rewrite history.

## 4. Right place for credentials

- Environment variables + OS credential stores (Windows Credential Manager, Linux secret manager, `chezoi`-style external prompts). Never a tracked file, never a committed `.env.example` with real values.

## 5. Report

- State what was scanned, what was found (or confirmed clean), and what you did about each finding.