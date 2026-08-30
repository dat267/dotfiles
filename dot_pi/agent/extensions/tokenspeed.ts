import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	let startTime = 0;
	let totalOutput = 0;

	pi.on("turn_start", async () => {
		if (startTime === 0) startTime = Date.now();
	});

	pi.on("turn_end", async (event) => {
		const m = event.message;
		if (m.role === "assistant" && m.usage) {
			totalOutput += m.usage.output;
		}
	});

	pi.on("agent_settled", async (_event, ctx) => {
		if (startTime === 0) return;
		const elapsed = Date.now() - startTime;
		const secs = (elapsed / 1000).toFixed(1);
		const tps = totalOutput > 0 && elapsed > 0
			? Math.round((totalOutput / elapsed) * 1000)
			: 0;
		ctx.ui.notify(`⏱ ${secs}s · ${tps} t/s`, "info");
		startTime = 0;
		totalOutput = 0;
	});
}