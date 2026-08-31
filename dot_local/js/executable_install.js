#!/usr/bin/env node
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const JS_DIR = path.resolve(__dirname);
const BIN_DIR = path.resolve(process.env.HOME, ".local/bin");

function run(cmd, opts = {}) {
  console.log(`[Running] ${cmd}`);
  execSync(cmd, { cwd: JS_DIR, stdio: "inherit", ...opts });
}

function link(exe) {
  const src = path.join(JS_DIR, "node_modules", ".bin", exe);
  const dst = path.join(BIN_DIR, exe);
  if (fs.existsSync(src)) {
    try {
      fs.unlinkSync(dst);
    } catch {}
    fs.symlinkSync(src, dst);
    console.log(`[Linked] ${dst} -> ${src}`);
  }
}

if (!fs.existsSync(path.join(JS_DIR, "node_modules", "playwright"))) {
  run("npm install");
} else {
  console.log("[Skip] node_modules exists, run 'npm update' to refresh");
}

run("npx playwright install --with-deps chromium");

link("playwright");
link("playwright.sh");

console.log("[Done] Playwright installed. Browsers in ~/.cache/ms-playwright/");