// Dates, times and numbers as the page writes them. Everything is UTC and written out, so no one
// has to guess the order of day and month, and the server's locale never shows.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function parts(value: string | Date): { day: number; month: string; year: number } {
  // A bare day ("2026-11-20") is read as that UTC day.
  const date =
    typeof value === "string"
      ? new Date(value.length === 10 ? `${value}T00:00:00Z` : value)
      : value;
  return { day: date.getUTCDate(), month: MONTHS[date.getUTCMonth()], year: date.getUTCFullYear() };
}

/** "20 Nov 2026" */
export function formatDay(value: string | Date): string {
  const { day, month, year } = parts(value);
  return `${day} ${month} ${year}`;
}

/** "20 Nov" */
export function formatDayShort(value: string | Date): string {
  const { day, month } = parts(value);
  return `${day} ${month}`;
}

/** "14:02 UTC" */
export function formatTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const two = (n: number): string => String(n).padStart(2, "0");
  return `${two(date.getUTCHours())}:${two(date.getUTCMinutes())} UTC`;
}

/** The UTC day of a moment, as "2026-11-20". */
export function utcDay(value: Date): string {
  return value.toISOString().slice(0, 10);
}

/** The UTC day `days` after (or before) a day written "2026-11-20". */
export function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return utcDay(date);
}

/** "6,200" */
export function formatCount(value: number): string {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** "0.04%", "41%": the number as it is held, with no digits added or dropped. */
export function formatPercent(value: number): string {
  return `${String(value)}%`;
}

/** "1 fix", "3 fixes" */
export function plural(count: number, one: string, many: string): string {
  return `${formatCount(count)} ${count === 1 ? one : many}`;
}
