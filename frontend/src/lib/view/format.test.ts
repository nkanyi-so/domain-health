import { describe, expect, it } from "vitest";
import {
  addDays,
  formatCount,
  formatDay,
  formatDayShort,
  formatPercent,
  formatTime,
  plural,
  utcDay,
} from "./format";

describe("dates and times", () => {
  it("writes a day out, day first, month in letters", () => {
    expect(formatDay("2026-11-20")).toBe("20 Nov 2026");
    expect(formatDay("2026-01-04")).toBe("4 Jan 2026");
    expect(formatDay("2026-11-19T19:13:49+00:00")).toBe("19 Nov 2026");
    expect(formatDayShort("2026-12-20")).toBe("20 Dec");
  });

  it("reads a moment as its UTC day, whatever offset it was written with", () => {
    expect(formatDay("2026-11-20T23:30:00-05:00")).toBe("21 Nov 2026");
    expect(utcDay(new Date("2026-11-20T23:59:59Z"))).toBe("2026-11-20");
  });

  it("writes a time as 24-hour UTC", () => {
    expect(formatTime("2026-11-20T14:02:00Z")).toBe("14:02 UTC");
    expect(formatTime("2026-11-20T09:05:59+00:00")).toBe("09:05 UTC");
    expect(formatTime("2026-11-20T01:02:00+02:00")).toBe("23:02 UTC");
  });

  it("moves a day forward and back across months and years", () => {
    expect(addDays("2026-11-20", 30)).toBe("2026-12-20");
    expect(addDays("2026-11-20", -1)).toBe("2026-11-19");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });
});

describe("numbers", () => {
  it("groups thousands and leaves a percentage as it is held", () => {
    expect(formatCount(6200)).toBe("6,200");
    expect(formatCount(144)).toBe("144");
    expect(formatCount(1234567)).toBe("1,234,567");
    expect(formatPercent(0.04)).toBe("0.04%");
    expect(formatPercent(41)).toBe("41%");
  });

  it("counts one thing and many", () => {
    expect(plural(1, "fix", "fixes")).toBe("1 fix");
    expect(plural(3, "fix", "fixes")).toBe("3 fixes");
    expect(plural(0, "listing", "listings")).toBe("0 listings");
  });
});
