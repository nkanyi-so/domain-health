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

export type Attempt = "ok" | "wrong" | "limited";

/**
 * One sign-in attempt, start to finish, with nothing awaited in between: the limit is asked, the
 * passphrase is compared, and a wrong one is counted before any other request can run. Asking
 * the limit, then waiting for anything, then counting let two hundred tries made at once all
 * through, since each saw the count before any of them had added to it.
 */
export function attempt(
  limiter: AttemptLimiter,
  address: string,
  now: number,
  right: () => boolean,
): Attempt {
  if (!limiter.allowed(address, now)) {
    return "limited";
  }
  if (right()) {
    return "ok";
  }
  limiter.failed(address, now);
  return "wrong";
}

export const signInLimiter: AttemptLimiter = new AttemptLimiter();
