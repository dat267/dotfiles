import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { registerNtfy } from "./index.ts";
import { makeFakePi } from "../testlib/fake-pi.ts";

function configure(fake: ReturnType<typeof makeFakePi>, topic: string | undefined, send: typeof fetch) {
	const agentDir = mkdtempSync(join(tmpdir(), "pi-ntfy-"));
	if (topic !== undefined) writeFileSync(join(agentDir, "ntfy.json"), JSON.stringify({ topic }), { mode: 0o600 });
	registerNtfy(fake.pi, { agentDir, fetch: send });
}

void describe("ntfy notification extension", () => {
	void it("loads topic from ntfy.json in Pi agent directory", async () => {
		const agentDir = mkdtempSync(join(tmpdir(), "pi-ntfy-"));
		writeFileSync(join(agentDir, "ntfy.json"), JSON.stringify({ topic: "file-topic" }), { mode: 0o600 });
		const fake = makeFakePi();
		const requests: string[] = [];
		registerNtfy(fake.pi, {
			agentDir,
			fetch: async (input) => {
				requests.push(String(input));
				return new Response(null, { status: 200 });
			},
		});
		await fake.emit("agent_settled", { aborted: false });
		assert.deepEqual(requests, ["https://ntfy.sh/file-topic"]);
	});

	void it("sends one generic notification after a non-aborted agent settles", async () => {
		const fake = makeFakePi();
		const requests: Array<{ url: string; init?: RequestInit }> = [];
		configure(fake, "private-topic", async (input, init) => {
			requests.push({ url: String(input), init });
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_end", { messages: [] });
		assert.equal(requests.length, 0, "agent_end may precede automatic continuation");
		await fake.emit("agent_settled", { aborted: false });

		assert.equal(requests.length, 1);
		assert.equal(requests[0].url, "https://ntfy.sh/private-topic");
		assert.equal(requests[0].init?.method, "POST");
		assert.equal(requests[0].init?.body, "Pi finished and is ready for your input.");
		assert.equal((requests[0].init?.headers as Record<string, string>).Title, "Pi is ready for input");
	});

	void it("sends final assistant text without tool-call commentary or thinking", async () => {
		const fake = makeFakePi();
		const requests: Array<{ body: string | null }> = [];
		configure(fake, "private-topic", async (_input, init) => {
			requests.push({ body: init?.body as string | null });
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_start", {});
		await fake.emit("agent_end", { messages: [
			{ role: "assistant", stopReason: "toolUse", content: [{ type: "text", text: "I am checking." }, { type: "toolCall" }] },
			{ role: "assistant", stopReason: "stop", content: [
				{ type: "thinking", thinking: "Do not send this reasoning." },
				{ type: "text", text: "Final result." },
			] },
		] });
		await fake.emit("agent_settled", { aborted: false });

		assert.equal(requests[0]?.body, "Final result.");
	});

	void it("prefers final-answer text blocks over signed commentary", async () => {
		const fake = makeFakePi();
		const requests: Array<{ body: string | null }> = [];
		configure(fake, "private-topic", async (_input, init) => {
			requests.push({ body: init?.body as string | null });
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_end", { messages: [{
			role: "assistant",
			stopReason: "stop",
			content: [
				{ type: "text", text: "Internal commentary.", textSignature: { v: 1, id: "commentary", phase: "commentary" } },
				{ type: "text", text: "Final answer.", textSignature: { v: 1, id: "final", phase: "final_answer" } },
			],
		}] });
		await fake.emit("agent_settled", { aborted: false });

		assert.equal(requests[0]?.body, "Final answer.");
	});

	void it("truncates long final answers to the notification limit", async () => {
		const fake = makeFakePi();
		const requests: Array<{ body: string | null }> = [];
		configure(fake, "private-topic", async (_input, init) => {
			requests.push({ body: init?.body as string | null });
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_start", {});
		await fake.emit("agent_end", { messages: [{
			role: "assistant",
			stopReason: "stop",
			content: [{ type: "text", text: "A".repeat(1_001) }],
		}] });
		await fake.emit("agent_settled", { aborted: false });

		assert.equal(requests[0]?.body?.length, 1_000);
		assert.equal(requests[0]?.body?.endsWith("…"), true);
	});

	void it("does not notify after an aborted run", async () => {
		const fake = makeFakePi();
		let calls = 0;
		configure(fake, "private-topic", async () => {
			calls++;
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_settled", { aborted: true });
		assert.equal(calls, 0);
	});

	void it("warns once when topic is not configured and sends nothing", async () => {
		const fake = makeFakePi();
		let calls = 0;
		configure(fake, undefined, async () => {
			calls++;
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_settled", { aborted: false });
		await fake.emit("agent_settled", { aborted: false });
		assert.equal(calls, 0);
		assert.equal(fake.calls.notifies.length, 1);
		assert.match(fake.calls.notifies[0].message, /ntfy\.json/);
	});

	void it("rejects topic values that could alter the ntfy path", async () => {
		const fake = makeFakePi();
		let calls = 0;
		configure(fake, "../other-topic", async () => {
			calls++;
			return new Response(null, { status: 200 });
		});

		await fake.emit("agent_settled", { aborted: false });
		assert.equal(calls, 0);
		assert.equal(fake.calls.notifies[0].level, "warning");
	});

	void it("reports delivery failure without throwing from settlement", async () => {
		const fake = makeFakePi();
		configure(fake, "private-topic", async () => {
			throw new Error("request failed for https://ntfy.sh/private-topic");
		});

		await assert.doesNotReject(fake.emit("agent_settled", { aborted: false }));
		assert.equal(fake.calls.notifies[0].level, "warning");
		assert.match(fake.calls.notifies[0].message, /network or timeout error/);
		assert.doesNotMatch(fake.calls.notifies[0].message, /private-topic/);
	});
});
