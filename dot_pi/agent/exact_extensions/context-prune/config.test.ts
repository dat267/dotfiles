import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadConfig, saveConfig } from "./config.ts";

test("loadConfig returns defaults when file missing", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cp-cfg-"));
  try {
    const cfg = await loadConfig(join(dir, "missing.json"));
    assert.deepEqual(cfg, { enabled: false, pruneOn: "agent-message" });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("loadConfig merges partial file over defaults", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cp-cfg-"));
  const path = join(dir, "settings.json");
  try {
    await saveConfig({ enabled: true, pruneOn: "agent-message" }, path);
    const cfg = await loadConfig(path);
    assert.deepEqual(cfg, { enabled: true, pruneOn: "agent-message" });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("saveConfig writes JSON that round-trips", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cp-cfg-"));
  const path = join(dir, "sub", "settings.json");
  try {
    await saveConfig({ enabled: true, pruneOn: "every-turn" }, path);
    const raw = await readFile(path, "utf-8");
    assert.deepEqual(JSON.parse(raw), { enabled: true, pruneOn: "every-turn" });
    assert.deepEqual(await loadConfig(path), { enabled: true, pruneOn: "every-turn" });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("loadConfig invalid JSON → defaults", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cp-cfg-"));
  const path = join(dir, "settings.json");
  try {
    const { writeFile } = await import("node:fs/promises");
    await writeFile(path, "{ not json");
    assert.deepEqual(await loadConfig(path), { enabled: false, pruneOn: "agent-message" });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("loadConfig rejects unknown pruneOn and non-boolean enabled", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cp-cfg-"));
  const path = join(dir, "settings.json");
  try {
    const { writeFile } = await import("node:fs/promises");
    await writeFile(path, JSON.stringify({ enabled: "yes", pruneOn: "bogus" }));
    const cfg = await loadConfig(path);
    assert.equal(cfg.enabled, false);
    assert.equal(cfg.pruneOn, "agent-message");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});