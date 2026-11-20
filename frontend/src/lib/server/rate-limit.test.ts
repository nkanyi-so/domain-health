import { describe, expect, it } from "vitest";
import { AttemptLimiter, OVERALL, PER_ADDRESS, WINDOW_MS, attempt } from "./rate-limit";

const A = "203.0.113.7";
const B = "203.0.113.8";

describe("the sign-in limit", () => {
  it("is five wrong tries from one address in ten minutes, thirty from everyone", () => {
    expect([PER_ADDRESS, OVERALL, WINDOW_MS]).toEqual([5, 30, 600_000]);
  });

  it("stops an address after its wrong tries, and leaves other addresses alone", () => {
    const limiter = new AttemptLimiter();
    for (let attempt = 0; attempt < PER_ADDRESS; attempt += 1) {
      expect(limiter.allowed(A, attempt)).toBe(true);
      limiter.failed(A, attempt);
    }

    expect(limiter.allowed(A, PER_ADDRESS)).toBe(false);
    expect(limiter.allowed(B, PER_ADDRESS)).toBe(true);
  });

  it("lets the address try again once the window has passed", () => {
    const limiter = new AttemptLimiter();
    for (let attempt = 0; attempt < PER_ADDRESS; attempt += 1) {
      limiter.failed(A, 0);
    }

    expect(limiter.allowed(A, WINDOW_MS - 1)).toBe(false);
    expect(limiter.allowed(A, WINDOW_MS)).toBe(true);
  });

  it("stops everyone once the overall count is reached, whatever address they use", () => {
    const limiter = new AttemptLimiter();
    for (let attempt = 0; attempt < OVERALL; attempt += 1) {
      limiter.failed(`198.51.100.${attempt}`, 0);
    }

    expect(limiter.allowed("192.0.2.1", 1)).toBe(false);
    expect(limiter.allowed("192.0.2.1", WINDOW_MS)).toBe(true);
  });
});

describe("one sign-in attempt", () => {
  it("lets at most five wrong tries made at once reach the passphrase", async () => {
    const limiter = new AttemptLimiter();
    let compared = 0;
    const wrong = (): boolean => {
      compared += 1;
      return false;
    };

    // As the route does it: everything that waits is awaited first, then the attempt is made.
    const outcomes = await Promise.all(
      Array.from({ length: 50 }, async () => {
        await Promise.resolve();
        await new Promise((resolve) => setTimeout(resolve, 0));
        return attempt(limiter, A, 0, wrong);
      }),
    );

    expect(compared).toBe(PER_ADDRESS);
    expect(outcomes.filter((outcome) => outcome === "wrong")).toHaveLength(PER_ADDRESS);
    expect(outcomes.filter((outcome) => outcome === "limited")).toHaveLength(50 - PER_ADDRESS);
  });

  it("does not look at the passphrase once the limit is reached", () => {
    const limiter = new AttemptLimiter();
    for (let n = 0; n < PER_ADDRESS; n += 1) {
      limiter.failed(A, 0);
    }
    let compared = 0;

    const outcome = attempt(limiter, A, 1, () => {
      compared += 1;
      return true;
    });

    expect(outcome).toBe("limited");
    expect(compared).toBe(0);
  });

  it("does not count a right passphrase", () => {
    const limiter = new AttemptLimiter();

    for (let n = 0; n < 20; n += 1) {
      expect(attempt(limiter, A, n, () => true)).toBe("ok");
    }
    expect(limiter.allowed(A, 20)).toBe(true);
  });
});
