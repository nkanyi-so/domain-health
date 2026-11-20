"use client";

// One button that names what it will do. The words are chosen by CSS from the theme in force
// (`.when-light`, `.when-dark` in globals.css), so the server and the browser draw the same
// thing and a saved choice never flashes.

import type { ReactElement } from "react";

type Theme = "light" | "dark";

function themeInForce(): Theme {
  const chosen = document.documentElement.getAttribute("data-theme");
  if (chosen === "light" || chosen === "dark") {
    return chosen;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function switchTheme(): void {
  const next: Theme = themeInForce() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try {
    window.localStorage.setItem("theme", next);
  } catch {
    // No storage: the choice lasts for this page only.
  }
}

export function ThemeSwitch(): ReactElement {
  return (
    <button type="button" className="btn btn-secondary btn-theme" onClick={switchTheme}>
      <span className="when-light">Dark theme</span>
      <span className="when-dark">Light theme</span>
    </button>
  );
}
