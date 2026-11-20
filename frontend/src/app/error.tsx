"use client";

import type { ReactElement } from "react";

/** Any page that fails to load for a reason the page itself has no words for. */
export default function PageError(): ReactElement {
  return (
    <main id="content" className="w-full max-w-content flex-1 px-4 py-8 wide:px-8">
      <h1 className="t-title">This page did not load</h1>
      <p className="mt-2">Something went wrong on our side. Reload the page.</p>
      <button
        type="button"
        className="btn btn-secondary mt-4"
        onClick={() => window.location.reload()}
      >
        Reload
      </button>
    </main>
  );
}
