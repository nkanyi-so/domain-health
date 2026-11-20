"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, type ReactElement, useEffect, useRef, useState } from "react";
import { Banner } from "./parts";

export type SignInState = "idle" | "refused" | "too-many" | "unavailable";

export interface SignInFormProps {
  initial: SignInState;
  /** A demo state is only drawn: the form then sends nothing and signs no one in. */
  demo: boolean;
}

function stateFor(status: number): SignInState | "signed-in" {
  if (status === 200) {
    return "signed-in";
  }
  if (status === 401) {
    return "refused";
  }
  return status === 429 ? "too-many" : "unavailable";
}

export function SignInForm({ initial, demo }: SignInFormProps): ReactElement {
  const [state, setState] = useState<SignInState>(initial);
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  // A page that opens already refused (the demo state) gives the field focus as a real one does.
  const refocus = useRef(initial === "refused");
  const router = useRouter();

  // After a refused sign-in the emptied field takes focus.
  useEffect(() => {
    if (refocus.current) {
      refocus.current = false;
      field.current?.focus();
    }
  });

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (demo || busy || !passphrase) {
      return;
    }
    setBusy(true);
    let next: SignInState | "signed-in";
    try {
      const response = await fetch("/api/admin/sign-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passphrase }),
      });
      next = stateFor(response.status);
    } catch {
      next = "unavailable";
    }
    if (next === "signed-in") {
      // The session changed: go to the client list and draw the chrome again as the admin.
      router.push("/");
      router.refresh();
      return;
    }
    refocus.current = true;
    setPassphrase("");
    setState(next);
    setBusy(false);
  }

  const refused = state === "refused";

  return (
    <div className="flex flex-col gap-4">
      {refused ? (
        <Banner tone="error" role="alert" id="sign-in-message" title="That passphrase is not right">
          <p>Nothing was changed. Try again.</p>
        </Banner>
      ) : null}
      {state === "too-many" ? (
        <Banner tone="notice" role="alert" id="sign-in-message" title="Too many tries">
          <p>Wait a few minutes before trying again.</p>
        </Banner>
      ) : null}
      {state === "unavailable" ? (
        <Banner
          tone="notice"
          role="alert"
          id="sign-in-message"
          title="Sign-in is not available now"
        >
          <p>Nothing was changed. Try again in a few minutes.</p>
        </Banner>
      ) : null}
      <form onSubmit={(event) => void submit(event)} noValidate className="flex flex-col gap-2">
        <label htmlFor="passphrase" className="t-small font-medium">
          Passphrase
        </label>
        <input
          ref={field}
          id="passphrase"
          name="passphrase"
          type="password"
          className="field field-plain"
          autoComplete="current-password"
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
          aria-invalid={refused ? "true" : undefined}
          aria-describedby={state === "idle" ? undefined : "sign-in-message"}
        />
        <button type="submit" className="btn btn-primary mt-2" aria-busy={busy}>
          Sign in
        </button>
      </form>
    </div>
  );
}
