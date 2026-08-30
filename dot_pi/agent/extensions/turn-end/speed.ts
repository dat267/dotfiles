/**
 * Token speed tracking per agent run (elapsed · tokens in · tokens out).
 *
 * `start()` is called on agent_start; `recordTurn()` accumulates usage from
 * each assistant turn; `computeStats()` returns the formatted run summary
 * and resets state.
 */

export interface RunStats {
	/** Human-readable stats line, e.g. `12.3s · 4.2k in · 1.1k out`. */
	formatted: string;
}

export class SpeedTracker {
	private runStart = 0;
	private runInput = 0;
	private runOutput = 0;

	start(): void {
		this.runStart = Date.now();
		this.runInput = 0;
		this.runOutput = 0;
	}

	recordTurn(usage: { input?: number; output?: number } | undefined): void {
		if (!usage) return;
		this.runInput += usage.input ?? 0;
		this.runOutput += usage.output ?? 0;
	}

	/** Compute the formatted stats line. Returns null if no run has started. */
	computeStats(): string | null {
		if (this.runStart === 0) return null;
		const secs = ((Date.now() - this.runStart) / 1000).toFixed(1);
		const fmt = (n: number) => (n < 1000 ? `${n}` : `${(n / 1000).toFixed(1)}k`);
		const formatted = `${secs}s · ${fmt(this.runInput)} in · ${fmt(this.runOutput)} out`;
		this.runStart = 0;
		this.runInput = 0;
		this.runOutput = 0;
		return formatted;
	}
}