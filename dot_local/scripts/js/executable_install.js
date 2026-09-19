#!/usr/bin/env node
// Install all dependencies for the JS scripts in this folder.
// Run from anywhere: node install.js
//
// - npm install (from package.json)
// - playwright install chromium (when playwright is a dependency)
//
// Deployed to ~/.local/scripts/js/install.js (already on PATH).

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DIR = dirname(fileURLToPath(import.meta.url));
const PKG_PATH = join(DIR, "package.json");

const color = {
  cyan: "\x1b[96m",
  green: "\x1b[92m",
  yellow: "\x1b[93m",
  red: "\x1b[91m",
  reset: "\x1b[0m",
};

function log(message, c) {
  const useColor = process.stdout.isTTY;
  console.log(useColor && c ? `${color[c]}${message}${color.reset}` : message);
}

function run(cmd, args, opts = {}) {
  log(`$ ${cmd} ${args.join(" ")}`, "cyan");
  const res = spawnSync(cmd, args, {
    cwd: DIR,
    stdio: "inherit",
    ...opts,
  });
  if (res.error) {
    log(`error running ${cmd}: ${res.error.message}`, "red");
    process.exit(1);
  }
  if (res.status !== 0) {
    log(`${cmd} failed with exit code ${res.status}`, "red");
    process.exit(res.status);
  }
}

function hasDependency(name) {
  if (!existsSync(PKG_PATH)) return false;
  const pkg = JSON.parse(readFileSync(PKG_PATH, "utf8"));
  return Boolean(
    (pkg.dependencies && pkg.dependencies[name]) ||
      (pkg.devDependencies && pkg.devDependencies[name])
  );
}

function npmBin() {
  const env = process.env.FNM_NODE;
  if (env) {
    const candidate = join(env, "bin", process.platform === "win32" ? "npm.cmd" : "npm");
    if (existsSync(candidate)) return candidate;
  }
  // Fall back to whatever npm is adjacent to the running node.
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

if (!existsSync(PKG_PATH)) {
  log("No package.json found in this folder; nothing to install.", "yellow");
  process.exit(0);
}

const npm = npmBin();
const pkg = JSON.parse(readFileSync(PKG_PATH, "utf8"));
log(`Setting up JS scripts in ${DIR}`, "cyan");
log(`  name: ${pkg.name || "(unnamed)"}`);

if (Object.keys(pkg.dependencies || {}).length || Object.keys(pkg.devDependencies || {}).length) {
  run(npm, ["install", "--no-fund", "--no-audit"]);
} else {
  log("No npm dependencies declared; skipping npm install.", "yellow");
}

if (hasDependency("playwright")) {
  log("playwright detected: installing chromium browser...", "cyan");
  const npx = process.platform === "win32" ? "npx.cmd" : "npx";
  run(npx, ["playwright", "install", "chromium"]);
}

log("Done. JS scripts ready.", "green");
