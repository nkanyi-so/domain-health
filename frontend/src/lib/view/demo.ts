// The demo flag: `?demo=<name>` makes a screen draw one fixed state. It only changes what is
// drawn: it never writes, never signs anyone in and never calls the backend.

export const DEMO_STATES = {
  list: ["loading", "fallback"],
  client: [
    "healthy",
    "fixes-only",
    "risks-only",
    "both",
    "handled-one",
    "all-handled",
    "risks-unavailable",
    "no-snapshot",
  ],
  check: ["running", "result", "refused", "rate-limited", "cap-reached"],
  admin: ["refused"],
} as const;

export type DemoScreen = keyof typeof DEMO_STATES;
export type DemoName<S extends DemoScreen> = (typeof DEMO_STATES)[S][number];

export type QueryValue = string | string[] | undefined;

export function firstValue(value: QueryValue): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** The demo state the address asks for, if this screen has one by that name. */
export function demoName<S extends DemoScreen>(screen: S, value: QueryValue): DemoName<S> | null {
  const name = firstValue(value);
  const names: readonly string[] = DEMO_STATES[screen];
  return name !== undefined && names.includes(name) ? (name as DemoName<S>) : null;
}

export function demoNotice(name: string): string {
  return `Showing a demo state: ${name}.`;
}
