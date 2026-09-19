/**
 * webreader/html.ts — dependency-free HTML to Markdown.
 *
 * Replaces the upstream extension's node-html-parser + turndown pair. The
 * walker is deliberately small and opinionated about what a model needs to
 * read: headings, paragraphs, absolute links, lists, code, quotes, tables.
 *
 * Two mechanics worth knowing before editing:
 *   - Preformatted text is lifted out into placeholders and restored after
 *     normalisation, so the whitespace-collapsing pass cannot flatten code.
 *   - List indentation and quote prefixes are emitted as sentinel characters
 *     (\u0002 indent) and resolved by that same normalisation pass, because
 *     the collapse pass strips ordinary leading whitespace per line.
 *
 * The failure that matters is silent content loss, so anything unrecognised
 * falls through as plain text rather than being dropped.
 */

const SKIP = new Set([
	"script", "style", "noscript", "template", "svg", "iframe",
	"head", "title", "meta", "link", "object", "embed", "canvas", "audio", "video",
]);
const VOID = new Set(["br", "hr", "img", "input", "source", "track", "wbr", "col"]);
const BLOCK = new Set([
	"address", "article", "aside", "blockquote", "details", "div", "dl", "dd", "dt",
	"fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
	"header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "summary", "table", "ul",
]);

const INDENT = "\u0002";
const PLACEHOLDER = "\u0000";

const ENTITIES: Record<string, string> = {
	amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", copy: "©", reg: "®",
	trade: "™", hellip: "…", mdash: "—", ndash: "–", lsquo: "‘", rsquo: "’",
	ldquo: "“", rdquo: "”", bull: "•", middot: "·", deg: "°", euro: "€", pound: "£",
	times: "×", plusmn: "±", laquo: "«", raquo: "»", sect: "§", para: "¶", dagger: "†",
	frac12: "½", frac14: "¼", frac34: "¾", larr: "←", rarr: "→", harr: "↔", rarr2: "⇒",
};

/** Decode named and numeric character references. Unknown names are left alone. */
export function decodeEntities(text: string): string {
	return text.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z][a-zA-Z0-9]*);/g, (match, body: string) => {
		if (body.startsWith("#x") || body.startsWith("#X")) {
			const code = parseInt(body.slice(2), 16);
			return Number.isFinite(code) && code > 0 ? String.fromCodePoint(code) : match;
		}
		if (body.startsWith("#")) {
			const code = parseInt(body.slice(1), 10);
			return Number.isFinite(code) && code > 0 ? String.fromCodePoint(code) : match;
		}
		return ENTITIES[body.toLowerCase()] ?? match;
	});
}

interface Token {
	kind: "text" | "open" | "close";
	tag?: string;
	attrs?: Record<string, string>;
	text?: string;
	start?: number;
	end?: number;
	selfClosing?: boolean;
}

const TAG_RE = /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<![^>]*>|<(\/?)([a-zA-Z][a-zA-Z0-9:-]*)((?:"[^"]*"|'[^']*'|[^>"'])*?)(\/?)>/g;
const ATTR_RE = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;

function parseAttrs(raw: string): Record<string, string> {
	const attrs: Record<string, string> = {};
	ATTR_RE.lastIndex = 0;
	let match: RegExpExecArray | null;
	while ((match = ATTR_RE.exec(raw)) !== null) {
		const name = match[1].toLowerCase();
		const value = match[2] ?? match[3] ?? match[4] ?? "";
		attrs[name] = decodeEntities(value);
	}
	return attrs;
}

function tokenize(html: string): Token[] {
	const tokens: Token[] = [];
	let last = 0;
	TAG_RE.lastIndex = 0;
	let match: RegExpExecArray | null;
	while ((match = TAG_RE.exec(html)) !== null) {
		if (match.index > last) {
			tokens.push({ kind: "text", text: html.slice(last, match.index) });
		}
		last = TAG_RE.lastIndex;
		if (match[1] === undefined && match[2] === undefined) continue; // comment, doctype, cdata
		const closing = match[1] === "/";
		const tag = match[2].toLowerCase();
		if (closing) {
			tokens.push({ kind: "close", tag, start: match.index, end: TAG_RE.lastIndex });
			continue;
		}
		const selfClosing = match[4] === "/" || VOID.has(tag);
		tokens.push({
			kind: "open",
			tag,
			attrs: parseAttrs(match[3] ?? ""),
			selfClosing,
			start: match.index,
			end: TAG_RE.lastIndex,
		});
	}
	if (last < html.length) tokens.push({ kind: "text", text: html.slice(last) });
	return tokens;
}

/** Slice out the first element matching `predicate`, tracking nested depth. */
function sliceElement(html: string, predicate: (token: Token) => boolean): string | null {
	const tokens = tokenize(html);
	for (let i = 0; i < tokens.length; i++) {
		const token = tokens[i];
		if (token.kind !== "open" || token.selfClosing || !predicate(token)) continue;
		let depth = 0;
		for (let j = i; j < tokens.length; j++) {
			const current = tokens[j];
			if (current.kind === "open" && current.tag === token.tag && !current.selfClosing) depth++;
			else if (current.kind === "close" && current.tag === token.tag) {
				depth--;
				if (depth === 0 && current.end !== undefined) return html.slice(token.start as number, current.end);
			}
		}
		return html.slice(token.start as number);
	}
	return null;
}

/**
 * Pick the element most likely to hold the page's own content, preferring
 * semantic containers over class-name guesses and falling back to the whole
 * document when nothing matches (never to an empty string).
 */
export function extractMain(html: string): string {
	const candidates: Array<(token: Token) => boolean> = [
		(token) => token.tag === "article",
		(token) => token.tag === "main",
		(token) => token.attrs?.role === "main",
		(token) => token.attrs?.id === "main-content",
		(token) => token.attrs?.id === "content",
		(token) => (token.attrs?.class ?? "").split(/\s+/).includes("markdown-body"),
		(token) => token.tag === "body",
	];
	for (const predicate of candidates) {
		const found = sliceElement(html, predicate);
		if (found) return found;
	}
	return html;
}

class Writer {
	private out: string[] = [];
	private pendingBreaks = 0;
	private preBlocks: string[] = [];

	/** Queue at least `count` newlines before the next content. */
	breakLines(count: number): void {
		if (count > this.pendingBreaks) this.pendingBreaks = count;
	}

	/** Start a fresh line, resolving queued breaks, quote prefix and list indent. */
	beginLine(quoteDepth: number, listDepth: number, marker?: string): void {
		while (this.pendingBreaks > 0) {
			this.out.push("\n");
			this.pendingBreaks--;
			// Blank lines inside a quote keep the quote visible (a bare newline
			// would end the block quote and reflow the rest as top-level text).
			if (this.pendingBreaks > 0 && quoteDepth > 1) {
				this.out.push(">".repeat(quoteDepth - 1));
			}
		}
		this.out.push(quoteDepth > 0 ? ">".repeat(quoteDepth) + " " : "");
		const indentDepth = marker === undefined ? listDepth : listDepth - 1;
		this.out.push(INDENT.repeat(Math.max(0, indentDepth)));
		if (marker !== undefined) this.out.push(marker);
	}

	/** True when the writer is mid-line (no queued breaks). */
	inline(quoteDepth: number, listDepth: number): void {
		if (this.pendingBreaks > 0 || this.out.length === 0) {
			this.beginLine(quoteDepth, listDepth);
		}
	}

	write(text: string): void {
		this.out.push(text);
	}

	/** Lift a fenced code block out of the normalisation path. */
	placeholder(code: string): string {
		this.preBlocks.push(code);
		return `${PLACEHOLDER}${this.preBlocks.length - 1}${PLACEHOLDER}`;
	}

	hasContent(): boolean {
		return this.out.length > 0 || this.pendingBreaks > 0;
	}

	render(): string {
		let text = this.out.join("");
		text = text.replace(/[ \t]+/g, " ");           // collapse runs (pre is lifted out)
		text = text.replace(/[ \t]+$/gm, "");          // trailing spaces per line
		text = text.replace(/^[ \t]+/gm, "");          // leading space, but not the indent sentinel
		text = text.replace(new RegExp(INDENT, "g"), "  ");
		text = text.replace(/\n{3,}/g, "\n\n");
		// Pre blocks come back last: their own indentation must not be touched by
		// the whitespace passes above, and the placeholder token survives them.
		text = text.replace(/\u0000(\d+)\u0000/g, (_, index: string) => this.preBlocks[Number(index)]);
		return text.trim();
	}
}

function fenceFor(code: string, language: string): string {
	const body = code.replace(/\n+$/, "");
	return `\`\`\`${language}\n${body}\n\`\`\``;
}

function absolute(ref: string, base: string): string {
	try {
		return new URL(ref, base).href;
	} catch {
		return ref;
	}
}

function isBlockTag(tag: string | undefined): boolean {
	return tag !== undefined && BLOCK.has(tag);
}

/** Convert one HTML document (or fragment) into Markdown. */
export function htmlToMarkdown(html: string, baseUrl: string): string {
	const tokens = tokenize(extractMain(html));
	const writer = new Writer();

	let skipDepth = 0;
	let preDepth = 0;
	let preLanguage = "";
	let preBuffer = "";
	let quoteDepth = 0;
	const listStack: Array<{ ordered: boolean; next: number }> = [];

	// Table capture: rows of cells, with the cell text collected separately.
	let tableDepth = 0;
	let tableRows: string[][] = [];
	let row: string[] | null = null;
	let cell: string[] | null = null;
	// Anchor hrefs pair with their own closing tag, so nested or interrupted
	// markup cannot swap URLs. null means "this anchor has no href": the text
	// stays, the brackets do not.
	const linkStack: Array<string | null> = [];

	const listDepth = () => listStack.length;
	// A block element directly inside an <li> arrives while the marker line is
	// still open; breaking there would strand the marker on its own line.
	let freshItem = false;
	const blockBreak = (count: number): void => {
		if (freshItem) { freshItem = false; return; }
		writer.breakLines(count);
	};

	const text = (raw: string): void => {
		if (cell) { cell.push(decodeEntities(raw)); return; }
		if (skipDepth > 0) return;
		if (preDepth > 0) { preBuffer += decodeEntities(raw); return; }
		if (tableDepth > 0) return; // table text lives in cells
		// Source newlines and runs are layout, not content; pre keeps its own.
		const value = decodeEntities(raw).replace(/\s+/g, " ");
		if (value.trim() === "") {
			// A whitespace-only run between inline elements is the word
			// separator ("**b** *i*"); emitting nothing would weld them
			// together. Trailing spaces are removed by render().
			if (writer.hasContent()) writer.write(" ");
			return;
		}
		freshItem = false;
		writer.inline(quoteDepth, listDepth());
		writer.write(value);
	};

	for (const token of tokens) {
		if (token.kind === "text") { text(token.text ?? ""); continue; }
		const tag = token.tag as string;

		if (token.kind === "open") {
			if (SKIP.has(tag)) {
				if (token.selfClosing) continue;
				skipDepth++;
				continue;
			}
			if (skipDepth > 0) continue;
			if (tag === "br") { writer.breakLines(1); continue; }
			if (tag === "hr") { blockBreak(2); writer.beginLine(quoteDepth, listDepth()); writer.write("---"); writer.breakLines(2); continue; }
			if (tag === "img") {
				const src = token.attrs?.src ?? "";
				const alt = token.attrs?.alt ?? "";
				if (src) { writer.inline(quoteDepth, listDepth()); writer.write(`![${alt}](${absolute(src, baseUrl)})`); }
				continue;
			}
			if (tag === "pre") {
				preDepth++;
				preBuffer = "";
				preLanguage = "";
				blockBreak(2);
				continue;
			}
			if (preDepth > 0 && tag === "code") {
				const cls = token.attrs?.class ?? "";
				const match = cls.match(/(?:language|lang)-([\w+#-]+)/);
				if (match && !preLanguage) preLanguage = match[1];
				continue;
			}
			if (tag === "table") { blockBreak(2); tableDepth++; tableRows = []; continue; }
			if (tableDepth > 0 && tag === "tr") { row = []; continue; }
			if (tableDepth > 0 && (tag === "td" || tag === "th")) { cell = []; continue; }
			if (tag === "blockquote") { blockBreak(2); quoteDepth++; continue; }
			if (tag === "ul" || tag === "ol") { listStack.push({ ordered: tag === "ol", next: 1 }); continue; }
			if (tag === "li") {
				const list = listStack[listStack.length - 1];
				const marker = list?.ordered ? `${list.next}. ` : "- ";
				if (list?.ordered) list.next++;
				writer.breakLines(1);
				writer.beginLine(quoteDepth, listDepth(), marker);
				freshItem = true;
				continue;
			}
			if (/^h[1-6]$/.test(tag)) { blockBreak(2); writer.beginLine(quoteDepth, listDepth()); writer.write("#".repeat(Number(tag[1])) + " "); continue; }
			if (tag === "p" || tag === "div" || tag === "section" || tag === "figcaption" || tag === "summary" || tag === "address" || tag === "dt") {
				blockBreak(2);
				if (tag === "dt") { writer.beginLine(quoteDepth, listDepth()); writer.write("**"); }
				continue;
			}
			if (tag === "dd") { writer.breakLines(1); writer.beginLine(quoteDepth, listDepth(), ": "); continue; }
			if (tag === "strong" || tag === "b") { writer.inline(quoteDepth, listDepth()); writer.write("**"); continue; }
			if (tag === "em" || tag === "i") { writer.inline(quoteDepth, listDepth()); writer.write("*"); continue; }
			if (tag === "del" || tag === "s" || tag === "strike") { writer.inline(quoteDepth, listDepth()); writer.write("~~"); continue; }
			if (tag === "code") { writer.inline(quoteDepth, listDepth()); writer.write("`"); continue; }
			if (tag === "a") {
				const href = token.attrs?.href ? absolute(token.attrs.href, baseUrl) : null;
				linkStack.push(href);
				writer.inline(quoteDepth, listDepth());
				if (href) writer.write("[");
				continue;
			}
			if (isBlockTag(tag)) { blockBreak(2); continue; }
			continue;
		}

		// close
		if (SKIP.has(tag)) { if (skipDepth > 0) skipDepth--; continue; }
		if (skipDepth > 0) continue;
		if (tag === "code" && preDepth === 0) { writer.write("`"); continue; }
		if (tag === "pre") {
			preDepth = Math.max(0, preDepth - 1);
			if (preDepth === 0) {
				const code = fenceFor(preBuffer, preLanguage);
				writer.inline(quoteDepth, listDepth());
				writer.write(writer.placeholder(code));
				writer.breakLines(2);
			}
			continue;
		}
		if (tag === "table") {
			tableDepth = Math.max(0, tableDepth - 1);
			if (tableDepth === 0 && tableRows.length > 0) {
				const width = Math.max(...tableRows.map((r) => r.length));
				const cellText = (value: string | undefined) => (value ?? "").replace(/\|/g, "\\|").trim();
				const line = (cells: string[]) => "| " + Array.from({ length: width }, (_, i) => cellText(cells[i])).join(" | ") + " |";
				const lines = [line(tableRows[0]), "| " + Array.from({ length: width }, () => "---").join(" | ") + " |"];
				for (const cells of tableRows.slice(1)) lines.push(line(cells));
				writer.inline(quoteDepth, listDepth());
				writer.write(lines.join("\n"));
				writer.breakLines(2);
			}
			tableRows = [];
			continue;
		}
		if (tableDepth > 0 && tag === "td") { if (cell && row) row.push(cell.join("")); cell = null; continue; }
		if (tableDepth > 0 && tag === "th") { if (cell && row) row.push(cell.join("")); cell = null; continue; }
		if (tableDepth > 0 && tag === "tr") { if (row) tableRows.push(row); row = null; continue; }
		if (tag === "blockquote") { quoteDepth = Math.max(0, quoteDepth - 1); writer.breakLines(2); continue; }
		if (tag === "ul" || tag === "ol") { listStack.pop(); writer.breakLines(listStack.length > 0 ? 1 : 2); continue; }
		if (tag === "li") { writer.breakLines(1); continue; }
		if (tag === "strong" || tag === "b") { writer.write("**"); continue; }
		if (tag === "em" || tag === "i") { writer.write("*"); continue; }
		if (tag === "del" || tag === "s" || tag === "strike") { writer.write("~~"); continue; }
		if (tag === "a") {
			const href = linkStack.pop() ?? null;
			if (href) writer.write(`](${href})`);
			continue;
		}
		if (tag === "dt") { writer.write("**"); continue; }
		if (/^h[1-6]$/.test(tag) || tag === "p" || tag === "div" || tag === "section" || tag === "figcaption" || tag === "summary") {
			writer.breakLines(2);
			continue;
		}
		if (isBlockTag(tag)) { writer.breakLines(2); continue; }
	}

	return writer.render();
}
