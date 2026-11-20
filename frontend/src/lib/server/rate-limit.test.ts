import { describe, expect, it } from "vitest";
import { AttemptLimiter, OVERALL, PER_ADDRESS, WINDOW_MS } from "./rate-limit";

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
