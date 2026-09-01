import { readFile, writeFile, mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { DEFAULT_CONFIG, PRUNE_ON_MODES, type ContextPruneConfig, type PruneOn } from "./types.ts";

/** Path to the extension's own settings file, independent of any project. */
export const SETTINGS_PATH = join(homedir(), ".pi", "agent", "context-prune", "settings.json");

function isPruneOn(value: unknown): value is PruneOn {
  return typeof value === "string" && PRUNE_ON_MODES.some((mode) => mode.value === value);
}

/** Reads the settings file and returns the config (or defaults on any failure). */
export async function loadConfig(path: string = SETTINGS_PATH): Promise<ContextPruneConfig> {
  try {
    const raw = await readFile(path, "utf-8");
    const existing = JSON.parse(raw);
    const merged = { ...DEFAULT_CONFIG, ...existing };
    return {
      enabled: typeof merged.enabled === "boolean" ? merged.enabled : DEFAULT_CONFIG.enabled,
      pruneOn: isPruneOn(merged.pruneOn) ? merged.pruneOn : DEFAULT_CONFIG.pruneOn,
    };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

/** Writes the full config to the settings file. */
export async function saveConfig(config: ContextPruneConfig, path: string = SETTINGS_PATH): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, JSON.stringify(config, null, 2));
}