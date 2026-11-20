"use client";

// The page's one polite live region. It sits in the layout, so it outlives a move between pages;
// anything on the page speaks through it with `announce`.

import { type ReactElement, useEffect, useRef } from "react";

const EVENT = "domain-health:announce";

export function announce(message: string): void {
  window.dispatchEvent(new CustomEvent<string>(EVENT, { detail: message }));
}

export function Announcer(): ReactElement {
  const region = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const say = (message: string): void => {
      if (region.current) {
        region.current.textContent = message;
      }
    };
    const heard = (event: Event): void => say((event as CustomEvent<string>).detail);
    window.addEventListener(EVENT, heard);
    return () => window.removeEventListener(EVENT, heard);
  }, []);

  return <div ref={region} role="status" aria-live="polite" className="sr-only" />;
}
