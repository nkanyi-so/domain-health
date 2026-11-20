"use client";

// The four links in the header. The current page's link is marked; a client's page marks none.

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactElement } from "react";

const LINKS: readonly { href: string; short: string; rest: string }[] = [
  { href: "/", short: "Clients", rest: "" },
  { href: "/check", short: "Check", rest: " a domain" },
  { href: "/evals", short: "Evals", rest: "" },
  { href: "/about", short: "About", rest: " this demo" },
];

export function NavLinks({ current }: { current: string | null }): ReactElement {
  return (
    <ul className="flex justify-between gap-4 wide:justify-start wide:gap-6">
      {LINKS.map((link) => (
        <li key={link.href}>
          <Link
            href={link.href}
            className="nav-link"
            aria-current={current === link.href ? "page" : undefined}
          >
            {link.short}
            {/* The longer names show at the wide breakpoint only. */}
            {link.rest ? (
              <span className="hidden whitespace-pre wide:inline">{link.rest}</span>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function CurrentNav(): ReactElement {
  return <NavLinks current={usePathname()} />;
}
