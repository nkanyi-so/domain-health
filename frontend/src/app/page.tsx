import type { ReactElement } from "react";
import { CLAIM } from "@/content/claim";

export default function Home(): ReactElement {
  return (
    <main className="mx-auto flex min-h-full w-full max-w-2xl flex-col justify-center gap-4 px-6 py-16">
      <h1 className="text-2xl font-semibold">domain-health</h1>
      <p className="text-lg">{CLAIM}</p>
      <p className="text-sm opacity-70">
        Nothing is built yet: this page is the scaffold. The client list, the live check and the
        eval table arrive in later phases.
      </p>
    </main>
  );
}
