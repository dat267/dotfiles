/**
 * modelpin/resolve.ts — turning a pin string into a concrete model.
 *
 * A pin accepts either form: "provider/modelId" (unambiguous by construction)
 * or a bare "modelId" resolved against the models pi has available.
 */

export interface ModelRef {
	provider: string;
	id: string;
}

export type Resolution =
	| { ok: true; model: ModelRef }
	| { ok: false; reason: string };

export function resolveModelRef(ref: string, models: ModelRef[], currentProvider?: string): Resolution {
	const slash = ref.indexOf("/");
	if (slash !== -1) {
		const provider = ref.slice(0, slash);
		const id = ref.slice(slash + 1);
		const hit = models.find((m) => m.provider === provider && m.id === id);
		return hit ? { ok: true, model: { provider: hit.provider, id: hit.id } } : { ok: false, reason: `no model ${ref}` };
	}

	const matches = models.filter((m) => m.id === ref);
	if (matches.length === 0) return { ok: false, reason: `no model "${ref}"` };
	if (matches.length === 1) return { ok: true, model: matches[0] };

	const preferred = currentProvider ? matches.find((m) => m.provider === currentProvider) : undefined;
	if (preferred) return { ok: true, model: preferred };
	const providers = matches.map((m) => m.provider).join(", ");
	return { ok: false, reason: `"${ref}" is ambiguous — pick one of: ${matches.map((m) => `${m.provider}/${m.id}`).join(", ")}` };
}