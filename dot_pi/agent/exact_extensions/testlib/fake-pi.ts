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
}

export interface FakePi {
	pi: any;
	ctx: any;
	calls: {
		entries: Array<{ entryType: string; data: unknown }>;
		messages: Array<{ message: unknown; opts: unknown }>;
		notifies: Array<{ message: string; level?: string }>;
		modelChanges: FakeModel[];
	};
	commands: Record<string, any>;
	runCommand: (name: string, args?: string) => Promise<void>;
	emit: (event: string, payload?: unknown) => Promise<void>;
}

export function makeFakePi(options: FakePiOptions = {}): FakePi {
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
	};

	const commands: Record<string, any> = {};

	const pi: any = {
		on: (event: string, fn: (event: unknown, ctx: unknown) => Promise<void>) => {
			const list = handlers.get(event) ?? [];
			list.push(fn);
			handlers.set(event, list);
		},
		appendEntry: (entryType: string, data: unknown) => calls.entries.push({ entryType, data }),
		sendMessage: (message: unknown, opts: unknown) => calls.messages.push({ message, opts }),
		registerCommand: (name: string, command: any) => {
			commands[name] = command;
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
		modelRegistry: {
			getAvailable: () => visible(),
			find: (provider: string, id: string) => visible().find((m) => m.provider === provider && m.id === id),
		},
		ui: {
			notify: (message: string, level?: string) => calls.notifies.push({ message, level }),
		},
	};

	return {
		pi,
		ctx,
		calls,
		commands,
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