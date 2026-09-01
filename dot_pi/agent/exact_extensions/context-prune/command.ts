import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
  DEFAULT_CONFIG,
  PRUNE_ON_MODES,
  type CapturedBatch,
  type ContextPruneConfig,
  type FlushResult,
} from "./types.ts";
import { saveConfig } from "./config.ts";

const SUBCOMMANDS = ["on", "off", "mode", "status", "now", "help"] as const;

const HELP_TEXT = `context-prune — summarize and prune raw tool outputs from future LLM context.

Subcommands:
  on            Enable pruning
  off           Disable pruning
  mode [value]  Show or set the prune trigger: ${PRUNE_ON_MODES.map((m) => m.value).join(" | ")}
  status        Show enabled state, trigger mode, and pending batch count
  now           Summarize + prune all pending tool-call batches immediately
  help          Show this help

Config is stored in ~/.pi/agent/context-prune/settings.json.
Pruned outputs are preserved in the session index; recover them anytime with
the context_tree_query tool using the short refs from each summary.`;

/**
 * Registers the /prune command: on/off/mode/status/now/help.
 * No TUI overlays — everything is a plain notification. state lives in
 * ~/.pi/agent/context-prune/settings.json and the session entries.
 */
export function registerPruneCommand(
  pi: ExtensionAPI,
  configRef: { value: ContextPruneConfig },
  flushPending: (ctx: any, delivery?: "runtime" | "session") => Promise<FlushResult>,
  capturePendingBatches: (ctx: any) => CapturedBatch[],
): void {
  pi.registerCommand("prune", {
    description: "Context-prune settings and commands",
    getArgumentCompletions(prefix: string) {
      const filtered = SUBCOMMANDS.filter((s) => s.startsWith(prefix));
      return filtered.length > 0 ? filtered.map((s) => ({ value: s, label: s })) : null;
    },
    async handler(args: string, ctx: any) {
      const parts = args.trim().split(/\s+/);
      const subcommand = parts[0] || undefined;
      const subArgs = parts.slice(1);

      switch (subcommand) {
        case "on": {
          configRef.value = { ...configRef.value, enabled: true };
          await saveConfig(configRef.value);
          ctx.ui.notify(`[prune] enabled — trigger: ${configRef.value.pruneOn}`, "info");
          break;
        }

        case "off": {
          configRef.value = { ...configRef.value, enabled: false };
          await saveConfig(configRef.value);
          ctx.ui.notify("[prune] disabled", "info");
          break;
        }

        case "mode": {
          const value = subArgs[0];
          if (!value) {
            ctx.ui.notify(`[prune] trigger: ${configRef.value.pruneOn} — usage: /prune mode ${PRUNE_ON_MODES.map((m) => m.value).join("|")}`, "info");
            break;
          }
          const mode = PRUNE_ON_MODES.find((m) => m.value === value);
          if (!mode) {
            ctx.ui.notify(`[prune] unknown mode "${value}" — expected: ${PRUNE_ON_MODES.map((m) => m.value).join(" | ")}`, "warning");
            break;
          }
          configRef.value = { ...configRef.value, pruneOn: mode.value };
          await saveConfig(configRef.value);
          ctx.ui.notify(`[prune] trigger set to ${mode.value}`, "info");
          break;
        }

        case "now": {
          const batches = capturePendingBatches(ctx);
          if (batches.length === 0) {
            ctx.ui.notify("[prune] nothing pending — no batches to summarize", "info");
            break;
          }
          const result = await flushPending(ctx, "runtime");
          if (result.ok) {
            ctx.ui.notify(
              `[prune] ${result.reason === "skipped-oversized" ? "skipped" : "pruned"} ${result.toolCallCount} tool call${result.toolCallCount === 1 ? "" : "s"} from ${result.batchCount} batch${result.batchCount === 1 ? "" : "es"} — summary ${result.summaryCharCount} chars vs ${result.rawCharCount} raw chars`,
              result.reason === "skipped-oversized" ? "warning" : "info",
            );
          } else if (result.reason === "already-flushing") {
            ctx.ui.notify("[prune] already summarizing — try again shortly", "info");
          } else if (result.reason === "empty") {
            ctx.ui.notify("[prune] nothing to prune", "info");
          } else {
            ctx.ui.notify(`[prune] flush failed: ${result.error ?? result.reason}`, "error");
          }
          break;
        }

        case "status": {
          const pending = capturePendingBatches(ctx).length;
          const cfg = configRef.value;
          ctx.ui.notify(
            `[prune] ${cfg.enabled ? "ON" : "OFF"} | trigger: ${cfg.pruneOn} | pending batches: ${pending} | settings: ~/.pi/agent/context-prune/settings.json (defaults: enabled ${DEFAULT_CONFIG.enabled}, mode ${DEFAULT_CONFIG.pruneOn})`,
            "info",
          );
          break;
        }

        case "help":
        default: {
          if (subcommand && subcommand !== "help") {
            ctx.ui.notify(`[prune] unknown subcommand "${subcommand}" — /prune help for usage`, "warning");
            break;
          }
          ctx.ui.notify(HELP_TEXT, "info");
          break;
        }
      }
    },
  });
}