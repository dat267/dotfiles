/**
 * Todo Extension - Demonstrates state management via session entries
 *
 * This extension:
 * - Registers a `todo` tool for the LLM to manage todos
 * - Registers a `/todos` command for users to view the list
 *
 * State is stored in tool result details (not external files), which allows
 * proper branching - when you branch, the todo state is automatically
 * correct for that point in history.
 */

import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";

interface Todo {
	id: number;
	text: string;
	done: boolean;
}

interface TodoDetails {
	action: "list" | "add" | "toggle" | "clear";
	todos: Todo[];
	nextId: number;
	error?: string;
}

const TodoParams = Type.Object({
	action: StringEnum(["list", "replace", "toggle", "clear"] as const),
	items: Type.Optional(Type.Array(Type.String({ description: "Todo text" }), { description: "Todo texts (for replace)" })),
	id: Type.Optional(Type.Number({ description: "Todo ID (for toggle)" })),
});

export default function (pi: ExtensionAPI) {
	// In-memory state (reconstructed from session on load)
	let todos: Todo[] = [];
	let nextId = 1;
	let widgetOn = false;
	const TODO_WIDGET = "todo-list";

	const widgetLines = (): string[] => {
		if (todos.length === 0) return ["todos: none"];
		const done = todos.filter((t) => t.done).length;
		const lines = [`todos ${done}/${todos.length}`];
		for (const t of todos) {
			lines.push(`${t.done ? "✓" : "○"} #${t.id} ${t.text}`);
		}
		return lines;
	};

	const refreshWidget = (ctx: ExtensionContext): void => {
		if (!widgetOn) return;
		ctx.ui.setWidget(TODO_WIDGET, widgetLines());
	};

	/**
	 * Reconstruct state from session entries.
	 * Scans tool results for this tool and applies them in order.
	 */
	const reconstructState = (ctx: ExtensionContext) => {
		todos = [];
		nextId = 1;

		for (const entry of ctx.sessionManager.getBranch()) {
			if (entry.type !== "message") continue;
			const msg = entry.message;
			if (msg.role !== "toolResult" || msg.toolName !== "todo") continue;

			const details = msg.details as TodoDetails | undefined;
			if (details) {
				todos = details.todos;
				nextId = details.nextId;
			}
		}
	};

	// Reconstruct state on session events
	pi.on("session_start", async (_event, ctx) => reconstructState(ctx));
	pi.on("session_tree", async (_event, ctx) => reconstructState(ctx));

	// Register the todo tool for the LLM
	pi.registerTool({
		name: "todo",
		label: "Todo",
		description: "Manage a todo list. Actions: list, replace (items), toggle (id), clear",
		promptSnippet: "Manage a structured todo list — replace, list, toggle, or clear",
		promptGuidelines: [
			"Use the todo tool to track multi-step tasks: call replace(items) with the full list of steps, then toggle them as you complete each step.",
			"replace overwrites the entire todo list — always pass the complete set of items.",
			"When the user asks for a plan with numbered steps, create todos for each step and check them off during implementation.",
			"When all todos are done, clear the list with todo(action: \"clear\") to keep session state tidy.",
		],
		parameters: TodoParams,

		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			switch (params.action) {
				case "list": {
					const text = todos.length
						? todos.map((t) => `[${t.done ? "x" : " "}] #${t.id}: ${t.text}`).join("\n")
						: "No todos";
					refreshWidget(ctx);
					return {
						content: [{ type: "text", text }],
						details: { action: "list", todos: [...todos], nextId } as TodoDetails,
					};
				}

				case "replace": {
					if (!params.items || params.items.length === 0) {
						return {
							content: [{ type: "text", text: "Error: items array required for replace" }],
							details: { action: "replace", todos: [...todos], nextId, error: "items required" } as TodoDetails,
						};
					}
					todos = params.items.map((text, i) => ({ id: i + 1, text, done: false }));
					nextId = todos.length + 1;
					refreshWidget(ctx);
					return {
						content: [{ type: "text", text: `Replaced todo list with ${todos.length} items` }],
						details: { action: "replace", todos: [...todos], nextId } as TodoDetails,
					};
				}

				case "toggle": {
					if (params.id === undefined) {
						return {
							content: [{ type: "text", text: "Error: id required for toggle" }],
							details: { action: "toggle", todos: [...todos], nextId, error: "id required" } as TodoDetails,
						};
					}
					const todo = todos.find((t) => t.id === params.id);
					if (!todo) {
						return {
							content: [{ type: "text", text: `Todo #${params.id} not found` }],
							details: {
								action: "toggle",
								todos: [...todos],
								nextId,
								error: `#${params.id} not found`,
							} as TodoDetails,
						};
					}
					todo.done = !todo.done;
					const status = todo.done ? "completed" : "uncompleted";
					refreshWidget(ctx);
					return {
						content: [{ type: "text", text: `Todo #${todo.id} ${status}: ${todo.text}` }],
						details: { action: "toggle", todos: [...todos], nextId } as TodoDetails,
					};
				}

				case "clear": {
					const count = todos.length;
					todos = [];
					nextId = 1;
					refreshWidget(ctx);
					return {
						content: [{ type: "text", text: `Cleared ${count} todos` }],
						details: { action: "clear", todos: [], nextId: 1 } as TodoDetails,
					};
				}

				default:
					return {
						content: [{ type: "text", text: `Unknown action: ${params.action}` }],
						details: {
							action: "list",
							todos: [...todos],
							nextId,
							error: `unknown action: ${params.action}`,
						} as TodoDetails,
					};
			}
		},

		renderCall(args, theme, _context) {
			let text = theme.fg("toolTitle", theme.bold("todo ")) + theme.fg("muted", args.action);
			if (args.items) text += ` ${theme.fg("dim", `[${args.items.length} items]`)}`;
			if (args.id !== undefined) text += ` ${theme.fg("accent", `#${args.id}`)}`;
			return new Text(text, 0, 0);
		},

		renderResult(result, { expanded }, theme, _context) {
			const details = result.details as TodoDetails | undefined;
			if (!details) {
				const text = result.content[0];
				return new Text(text?.type === "text" ? text.text : "", 0, 0);
			}

			if (details.error) {
				return new Text(theme.fg("error", `Error: ${details.error}`), 0, 0);
			}

			const todoList = details.todos;

			switch (details.action) {
				case "list": {
					if (todoList.length === 0) {
						return new Text(theme.fg("dim", "No todos"), 0, 0);
					}
					let listText = theme.fg("muted", `${todoList.length} todo(s):`);
					const display = expanded ? todoList : todoList.slice(0, 5);
					for (const t of display) {
						const check = t.done ? theme.fg("success", "✓") : theme.fg("dim", "○");
						const itemText = t.done ? theme.fg("dim", t.text) : theme.fg("muted", t.text);
						listText += `\n${check} ${theme.fg("accent", `#${t.id}`)} ${itemText}`;
					}
					if (!expanded && todoList.length > 5) {
						listText += `\n${theme.fg("dim", `... ${todoList.length - 5} more`)}`;
					}
					return new Text(listText, 0, 0);
				}

				case "replace": {
					return new Text(
						theme.fg("success", "✓ ") +
							theme.fg("muted", `Replaced with ${todoList.length} todos`),
						0,
						0,
					);
				}

				case "toggle": {
					const text = result.content[0];
					const msg = text?.type === "text" ? text.text : "";
					return new Text(theme.fg("success", "✓ ") + theme.fg("muted", msg), 0, 0);
				}

				case "clear":
					return new Text(theme.fg("success", "✓ ") + theme.fg("muted", "Cleared all todos"), 0, 0);
			}
		},
	});

	// Register the /todos command for users
	pi.registerCommand("todos", {
		description: "Toggle the todo widget (second call hides it)",
		handler: async (_args, ctx) => {
			widgetOn = !widgetOn;
			if (widgetOn) ctx.ui.setWidget(TODO_WIDGET, widgetLines());
			else ctx.ui.setWidget(TODO_WIDGET, undefined);
		},
	});
}
