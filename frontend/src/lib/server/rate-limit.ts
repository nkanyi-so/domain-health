// Sign-in attempts, counted in memory. One server instance keeps its own counts, which is enough
// for a one-person demo: the limit slows guessing, the passphrase is what keeps the door shut.

export const WINDOW_MS: number = 10 * 60 * 1000;
/** Wrong passphrases allowed from one address in a window. */
export const PER_ADDRESS = 5;
/** Wrong passphrases allowed from everyone together in a window, per server instance. */
export const OVERALL = 30;

const EVERYONE = "*";

export class AttemptLimiter {
  private readonly failures = new Map<string, number[]>();

  constructor(
    private readonly perAddress: number = PER_ADDRESS,
    private readonly overall: number = OVERALL,
    private readonly windowMs: number = WINDOW_MS,
  ) {}

  private recent(key: string, now: number): number[] {
    const kept = (this.failures.get(key) ?? []).filter((at) => now - at < this.windowMs);
    if (kept.length === 0) {
      this.failures.delete(key);
    } else {
      this.failures.set(key, kept);
    }
    return kept;
  }

  /** May this address try now? Asked before the passphrase is looked at. */
  allowed(address: string, now: number): boolean {
    return (
      this.recent(address, now).length < this.perAddress &&
      this.recent(EVERYONE, now).length < this.overall
    );
  }

  /** A wrong passphrase. A right one is not counted and clears nothing. */
  failed(address: string, now: number): void {
    for (const key of [address, EVERYONE]) {
      this.failures.set(key, [...this.recent(key, now), now]);
    }
  }
}

export const signInLimiter: AttemptLimiter = new AttemptLimiter();
