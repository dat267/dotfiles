/**
 * Tests for webreader/html.ts — dependency-free HTML to Markdown.
 *
 * This replaces the upstream extension's node-html-parser + turndown pair
 * (2 runtime deps) with a tag walker that covers what a model actually
 * reads: headings, paragraphs, links made absolute so they stay clickable
 * and followable, lists, code, quotes and tables. The failure that matters
 * is silent content loss — a walker that drops a section still produces
 * plausible output — so the cases below pin the elements that carry text.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { extractMain, htmlToMarkdown } from "./html.ts";

const BASE = "https://example.com/docs/page";

function md(html: string, base = BASE): string {
	return htmlToMarkdown(html, base);
}

void describe("block structure", () => {
	void it("renders ATX headings", () => {
		assert.equal(md("<h1>Title</h1>"), "# Title");
		assert.equal(md("<h3>Sub</h3>"), "### Sub");
	});

	void it("separates paragraphs with a blank line", () => {
		assert.equal(md("<p>one</p><p>two</p>"), "one\n\ntwo");
	});

	void it("turns br into a line break inside the paragraph", () => {
		assert.equal(md("<p>a<br>b</p>"), "a\nb");
	});

	void it("renders hr as a rule", () => {
		assert.equal(md("<p>a</p><hr><p>b</p>"), "a\n\n---\n\nb");
	});

	void it("collapses insignificant whitespace but keeps words apart", () => {
		assert.equal(md("<p>a\n   b\t\tc</p>"), "a b c");
		assert.equal(md("<div>a</div><div>b</div>"), "a\n\nb");
	});

	void it("ignores empty elements without emitting blank blocks", () => {
		assert.equal(md("<p></p><p>a</p><div> </div>"), "a");
	});
});

void describe("inline markup", () => {
	void it("renders strong and em", () => {
		assert.equal(md("<p><strong>bold</strong> and <em>it</em></p>"), "**bold** and *it*");
		assert.equal(md("<p><b>b</b> <i>i</i></p>"), "**b** *i*");
	});

	void it("renders inline code", () => {
		assert.equal(md("<p>use <code>npm test</code></p>"), "use `npm test`");
	});

	void it("renders strikethrough", () => {
		assert.equal(md("<p><del>gone</del></p>"), "~~gone~~");
	});

	void it("decodes named and numeric entities", () => {
		assert.equal(md("<p>a &amp; b &lt;c&gt; &quot;d&quot; &#65; &#x42;</p>"), 'a & b <c> "d" A B');
		assert.equal(md("<p>x&nbsp;y</p>"), "x y");
	});
});

void describe("links and images", () => {
	void it("makes root-relative links absolute", () => {
		assert.equal(md('<a href="/api">api</a>'), `[api](https://example.com/api)`);
	});

	void it("resolves document-relative links against the page URL", () => {
		assert.equal(md('<a href="other.html">o</a>'), "[o](https://example.com/docs/other.html)");
		assert.equal(md('<a href="../up">u</a>'), "[u](https://example.com/up)");
	});

	void it("keeps absolute and mailto links", () => {
		assert.equal(md('<a href="https://other.test/x">x</a>'), "[x](https://other.test/x)");
		assert.equal(md('<a href="mailto:a@b.c">mail</a>'), "[mail](mailto:a@b.c)");
	});

	void it("resolves fragments against the base", () => {
		assert.equal(md('<a href="#sec">s</a>'), "[s](https://example.com/docs/page#sec)");
	});

	void it("renders images with alt text", () => {
		assert.equal(md('<img src="/i.png" alt="diagram">'), "![diagram](https://example.com/i.png)");
	});

	void it("renders a bare link when the text is the URL", () => {
		assert.equal(md('<a href="https://x.test/a">https://x.test/a</a>'), "[https://x.test/a](https://x.test/a)");
	});
});

void describe("lists", () => {
	void it("renders unordered lists", () => {
		assert.equal(md("<ul><li>a</li><li>b</li></ul>"), "- a\n- b");
	});

	void it("renders ordered lists with numbers", () => {
		assert.equal(md("<ol><li>a</li><li>b</li></ol>"), "1. a\n2. b");
	});

	void it("indents nested lists", () => {
		assert.equal(md("<ul><li>a<ul><li>a1</li></ul></li><li>b</li></ul>"), "- a\n  - a1\n- b");
	});

	void it("keeps multi-paragraph list items readable", () => {
		assert.equal(md("<ul><li><p>a</p><p>b</p></li></ul>"), "- a\n\n  b");
	});
});

void describe("code and quotes", () => {
	void it("fences code blocks and preserves their whitespace", () => {
		assert.equal(md("<pre><code>a\n  b\n</code></pre>"), "```\na\n  b\n```");
	});

	void it("uses the language class as an info string when present", () => {
		assert.equal(md('<pre><code class="language-ts">const a = 1;</code></pre>'), "```ts\nconst a = 1;\n```");
	});

	void it("quotes blockquote content and nests it", () => {
		assert.equal(md("<blockquote><p>quoted</p></blockquote>"), "> quoted");
		assert.equal(md("<blockquote><p>a</p><blockquote><p>b</p></blockquote></blockquote>"), "> a\n>\n>> b");
	});
});

void describe("tables", () => {
	void it("renders a header row and separator", () => {
		assert.equal(
			md("<table><tr><th>h1</th><th>h2</th></tr><tr><td>a</td><td>b</td></tr></table>"),
			"| h1 | h2 |\n| --- | --- |\n| a | b |",
		);
	});

	void it("promotes a header-less first row so the table still renders", () => {
		assert.equal(md("<table><tr><td>a</td></tr></table>"), "| a |\n| --- |");
	});
});

void describe("noise removal", () => {
	void it("drops script, style, noscript, svg and iframe content", () => {
		assert.equal(
			md("<style>p{color:red}</style><script>var x=1;</script><p>keep</p><noscript>n</noscript><svg><path/></svg><iframe src='/f'></iframe>"),
			"keep",
		);
	});

	void it("drops comments and the document head", () => {
		assert.equal(md("<head><title>T</title><meta charset='utf-8'></head><body><!-- c --><p>a</p></body>"), "a");
	});

	void it("returns an empty string for empty input", () => {
		assert.equal(md(""), "");
		assert.equal(md("   "), "");
	});
});

void describe("extractMain", () => {
	void it("prefers article over surrounding chrome", () => {
		const html = "<nav>menu</nav><article><p>body</p></article><footer>f</footer>";
		assert.equal(md(html), "body");
	});

	void it("prefers main when there is no article", () => {
		assert.equal(md("<header>h</header><main><p>m</p></main>"), "m");
	});

	void it("uses the body when no container matches", () => {
		assert.equal(md("<div><p>plain</p></div>"), "plain");
	});

	void it("keeps markdown-ish containers whole", () => {
		assert.equal(md('<div class="markdown-body"><p>x</p><p>y</p></div>'), "x\n\ny");
	});
});

void describe("htmlToMarkdown end to end", () => {
	void it("converts a realistic page without losing its sections", () => {
		const html = `<!doctype html>
<html><head><title>Doc</title><style>.x{}</style></head>
<body>
<nav>Skip this nav</nav>
<article>
  <h1>Getting started</h1>
  <p>Install with <code>npm i</code> then read <a href="/guide">the guide</a>.</p>
  <h2>Steps</h2>
  <ol><li>One</li><li>Two</li></ol>
  <pre><code>run --now</code></pre>
  <blockquote><p>Note this</p></blockquote>
</article>
<footer>Footer junk</footer>
</body></html>`;
		const out = md(html);
		assert.match(out, /^# Getting started$/m);
		assert.match(out, /Install with `npm i` then read \[the guide\]\(https:\/\/example\.com\/guide\)\./);
		assert.match(out, /^## Steps$/m);
		assert.match(out, /^1\. One$/m);
		assert.match(out, /^```\nrun --now\n```$/m);
		assert.match(out, /^> Note this$/m);
		assert.doesNotMatch(out, /Skip this nav|Footer junk|\.x\{\}/);
	});
});

void describe("extractMain is exported for callers that need the raw slice", () => {
	void it("returns the article html", () => {
		assert.equal(extractMain("<nav>n</nav><article><p>a</p></article>"), "<article><p>a</p></article>");
	});
});
