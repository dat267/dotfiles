/**
 * fake-pi — the host-semantics fake shared by extension tests.
 *
 * One factory encoding pi's runtime semantics once, so suites stop
 * re-deriving them by hand (and drifting apart). Semantics land here
 * one failing test at a time.
 */

export interface FakeModel {
	provider: string;
	id: string;
	contextWindow?: number;
}

export interface FakePiOptions {
	/** The availability snapshot the registry reports. */
	catalog?: FakeModel[];
	/** ms until the snapshot becomes visible — models pi's async
	 *  availability refresh, which is still in flight at session_start. */
	availableAfterMs?: number;
	/** Initial ctx.model. */
	current?: FakeModel;
	/** Durable entries replayed via ctx.sessionManager.getBranch(). */
	entries?: unknown[];
}

export interface FakePi {
	pi: any;
	ctx: any;
	calls: {
		entries: Array<{ entryType: string; data: unknown }>;
		messages: Array<{ message: unknown; opts: unknown }>;
		notifies: Array<{ message: string; level?: string }>;
		modelChanges: FakeModel[];
		/** Live kind-tagged stream of every captured host call and registration. */
		all: Array<{ kind: string; [k: string]: unknown }>;
	};
	commands: Record<string, any>;
	tools: Record<string, any>;
	entryRenderers: Record<string, any>;
	messageRenderers: Record<string, any>;
	/** Live view: first handler registered per event. */
	handlers: Record<string, (event: unknown, ctx: unknown) => Promise<void>>;
	runCommand: (name: string, args?: string) => Promise<void>;
	emit: (event: string, payload?: unknown) => Promise<void>;
}

export function makeFakePi(options: FakePiOptions = {}): FakePi {
	let activeTools: string[] = [];
	const all: Array<{ kind: string; [k: string]: unknown }> = [];
	const catalog = options.catalog ?? [];
	const readyAt = Date.now() + (options.availableAfterMs ?? 0);
	const visible = () => (Date.now() >= readyAt ? catalog : []);
	let current = options.current;
	const handlers = new Map<string, Array<(event: unknown, ctx: unknown) => Promise<void>>>();
	const calls = {
		entries: [] as Array<{ entryType: string; data: unknown }>,
		messages: [] as Array<{ message: unknown; opts: unknown }>,
		notifies: [] as Array<{ message: string; level?: string }>,
		modelChanges: [] as FakeModel[],
		all,
	};

	const commands: Record<string, any> = {};
	const tools: Record<string, any> = {};
	const entryRenderers: Record<string, any> = {};
	const messageRenderers: Record<string, any> = {};

	const pi: any = {
		on: (event: string, fn: (event: unknown, ctx: unknown) => Promise<void>) => {
			const list = handlers.get(event) ?? [];
			list.push(fn);
			handlers.set(event, list);
		},
		appendEntry: (entryType: string, data: unknown) => {
			const record = { kind: "appendEntry", entryType, data };
			all.push(record);
			calls.entries.push(record);
		},
		sendMessage: (message: unknown, opts: unknown) => {
			const record = { kind: "sendMessage", message, opts };
			all.push(record);
			calls.messages.push(record);
		},
		registerCommand: (name: string, command: any) => {
			commands[name] = command;
			all.push({ kind: "command", name, command });
		},
		registerTool: (tool: any) => {
			tools[tool.name] = tool;
			all.push({ kind: "tool", tool });
		},
		registerEntryRenderer: (customType: string, fn: any) => {
			entryRenderers[customType] = fn;
			all.push({ kind: "entryRenderer", customType, fn });
		},
		registerMessageRenderer: (customType: string, fn: any) => {
			messageRenderers[customType] = fn;
			all.push({ kind: "messageRenderer", customType, fn });
		},
		getActiveTools: () => [...activeTools],
		setActiveTools: (names: string[]) => {
			activeTools = [...names];
			all.push({ kind: "setActiveTools", names });
		},
		// pi's extension-API setModel: refuses (false) while the provider has no
		// availability snapshot — it must not change the model nor emit. On
		// success it updates the current model and emits model_select "set"
		// with the previous model, exactly like AgentSession.setModel.
		setModel: async (model: FakeModel) => {
			if (!visible().some((m) => m.provider === model.provider && m.id === model.id)) return false;
			const previousModel = current;
			current = model;
			calls.modelChanges.push(model);
			for (const fn of handlers.get("model_select") ?? []) {
				await fn({ model, previousModel, source: "set" }, ctx);
			}
			return true;
		},
	};

	const ctx: any = {
		get model() {
			return current;
		},
		sessionManager: {
			getBranch: () => options.entries ?? [],
		},
		getContextUsage: () => ({ tokens: 100_000, contextWindow: 1_000_000, percent: 10 }),
		signal: { aborted: false },
		modelRegistry: {
			getAvailable: () => visible(),
			find: (provider: string, id: string) => visible().find((m) => m.provider === provider && m.id === id),
		},
		ui: {
			// Identity styling — assertions verify structure, not color codes.
			theme: { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t },
			notify: (message: string, level?: string) => calls.notifies.push({ message, level }),
			setStatus: (key: string, value: unknown) => all.push({ kind: "setStatus", key, value }),
			setWidget: (key: string, value: unknown) => all.push({ kind: "setWidget", key, value }),
		},
	};

	return {
		pi,
		ctx,
		calls,
		commands,
		tools,
		entryRenderers,
		messageRenderers,
		// Live view — a snapshot taken here would miss every handler the
		// extension registers after makeFakePi returns.
		get handlers() {
			return Object.fromEntries([...handlers].map(([event, fns]) => [event, fns[0]]));
		},
		runCommand: async (name: string, args = "") => {
			const command = commands[name];
			if (!command) throw new Error(`no command registered as "${name}"`);
			await command.handler(args, ctx);
		},
		emit: async (event: string, payload?: unknown) => {
			for (const fn of handlers.get(event) ?? []) await fn(payload, ctx);
		},
	};
}