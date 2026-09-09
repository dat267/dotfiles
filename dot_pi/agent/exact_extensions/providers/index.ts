/**
 * Providers extension for pi — consolidated provider registrations.
 *
 * Each provider lives in its own module and exports a register function.
 * Auth per provider: ~/.pi/agent/auth.json (keyed by provider id) or env var.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { registerCharmHyper } from "./hyper/index.ts";
import { registerClinePass } from "./cline-pass/index.ts";
import { registerWindowsCopilot } from "./windows-copilot/index.ts";

export default function (pi: ExtensionAPI) {
	registerCharmHyper(pi);
	registerClinePass(pi);
	registerWindowsCopilot(pi);
}
