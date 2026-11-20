import type { Metadata } from "next";
import { type ReactElement, Suspense } from "react";
import { PageFrame, ServiceStrip } from "@/components/chrome";
import { SignInForm } from "@/components/sign-in-form";
import { demoName } from "@/lib/view/demo";

export const metadata: Metadata = { title: "Admin sign-in" };

function Screen({ demo }: { demo: string | null }): ReactElement {
  return (
    <PageFrame strip={<ServiceStrip />} demo={demo}>
      <div className="flex max-w-field flex-col gap-4">
        <h1 className="t-title">Admin sign-in</h1>
        <p>
          For the owner. Signing in lets handled and reopen change the shared list. Visitors do not
          need to sign in.
        </p>
        <SignInForm key={demo ?? "live"} initial={demo ? "refused" : "idle"} demo={demo !== null} />
      </div>
    </PageFrame>
  );
}

async function SignIn({
  searchParams,
}: Pick<PageProps<"/admin">, "searchParams">): Promise<ReactElement> {
  return <Screen demo={demoName("admin", (await searchParams).demo)} />;
}

export default function Page({ searchParams }: PageProps<"/admin">): ReactElement {
  return (
    <Suspense fallback={<Screen demo={null} />}>
      <SignIn searchParams={searchParams} />
    </Suspense>
  );
}
