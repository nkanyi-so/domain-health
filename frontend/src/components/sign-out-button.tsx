"use client";

import { useRouter } from "next/navigation";
import { type ReactElement, useState } from "react";
import { announce } from "./announcer";

/** Signs the admin out, then returns to the client list, which says "Signed out." */
export function SignOutButton(): ReactElement {
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function signOut(): Promise<void> {
    if (busy) {
      return;
    }
    setBusy(true);
    try {
      const response = await fetch("/api/admin/sign-out", { method: "POST" });
      if (response.ok) {
        // The session changed: go to the client list and draw the chrome again as a visitor.
        router.push("/");
        router.refresh();
        announce("Signed out.");
        setBusy(false);
        return;
      }
    } catch {
      // Falls through: the button becomes usable again.
    }
    setBusy(false);
  }

  return (
    <button type="button" className="btn btn-quiet" onClick={signOut} aria-busy={busy}>
      Sign out
    </button>
  );
}
