// The six icons, drawn inline: 16 px, a 1.5 px stroke, the colour of the text they sit beside.
// Each is decoration for a word next to it, so each is hidden from a screen reader.

import type { ReactElement, ReactNode } from "react";

function Icon({ children }: { children: ReactNode }): ReactElement {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

const CIRCLE: ReactElement = <circle cx="8" cy="8" r="6.25" />;
const SQUARE: ReactElement = <rect x="1.75" y="1.75" width="12.5" height="12.5" rx="1.5" />;
const TICK: ReactElement = <path d="M5 8.25l2 2 4-4.5" />;

export function TickCircle(): ReactElement {
  return (
    <Icon>
      {CIRCLE}
      {TICK}
    </Icon>
  );
}

export function TickSquare(): ReactElement {
  return (
    <Icon>
      {SQUARE}
      {TICK}
    </Icon>
  );
}

export function EmptySquare(): ReactElement {
  return <Icon>{SQUARE}</Icon>;
}

export function CrossCircle(): ReactElement {
  return (
    <Icon>
      {CIRCLE}
      <path d="M5.75 5.75l4.5 4.5M10.25 5.75l-4.5 4.5" />
    </Icon>
  );
}

export function DashCircle(): ReactElement {
  return (
    <Icon>
      {CIRCLE}
      <path d="M5 8h6" />
    </Icon>
  );
}

export function InfoCircle(): ReactElement {
  return (
    <Icon>
      {CIRCLE}
      <path d="M8 7.5v3.25M8 5.1v.05" />
    </Icon>
  );
}
