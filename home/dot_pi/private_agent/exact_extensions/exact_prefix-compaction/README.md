# prefix-compaction

Pi compaction that reuses the model server's prefix cache, for DeepSeek models on the `openai-completions` and `anthropic-messages` wire formats.

Pi's default compaction serializes the whole history into one new user message under a summarizer system prompt. To a server with automatic prefix caching that is a brand-new prompt, so the entire history is prefilled cold before the summary starts. This extension keeps the last real provider request and replays it with one instruction appended: the prefix is byte-for-byte what the server just processed, so only the instruction is prefilled.

Keeping the cache warm between turns is not this extension's job. Pi does that itself through the model's `promptCache` lifetimes and the `cacheWarming` setting.

## Scope

DeepSeek only, matched on the model id, on the two wire formats whose payload can be rewritten. Every other model keeps Pi's default compaction.

No configuration file and no options. There is deliberately no way to change the thinking level for the summary: it is part of the prefix, and changing it re-prefills everything.

## Fallbacks

Pi's own compaction runs, unchanged, when there is no capture yet, the model changed since the capture, the capture came from Pi's own summarizer, the request is an overflow recovery, too little of the window is left, the summary request fails, the summary is empty, or the rebuilt request fails the prefix assertion. A capture is used for at most one compaction and never replayed afterwards.

## Files

- `core.ts`: pure logic, no Pi imports. Payload rewriting, the prefix assertion, the budget, cache reporting.
- `index.ts`: the Pi wiring. Captures and the summary request through the model registry.

## Tests

```bash
node --test core.test.ts index.test.ts
```
