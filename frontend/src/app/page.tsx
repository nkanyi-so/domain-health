import type { Metadata } from "next";
import { type ReactElement, Suspense } from "react";
import { ClientListScreen } from "@/components/client-list-screen";
import { demoClientList } from "@/data/demo-states";
import { FALLBACK } from "@/lib/fallback";
import { loadClientList } from "@/lib/server/data";
import { demoName } from "@/lib/view/demo";
import { clientListView } from "@/lib/view/screens";

// The layout's "%s - domain-health" reaches the screens below this one, not this one itself.
export const metadata: Metadata = { title: { absolute: "Clients - domain-health" } };

async function Clients({
  searchParams,
}: Pick<PageProps<"/">, "searchParams">): Promise<ReactElement> {
  const demo = demoName("list", (await searchParams).demo);
  if (demo) {
    return <ClientListScreen view={demoClientList(demo)} demo={demo} />;
  }
  return <ClientListScreen view={clientListView(await loadClientList(), FALLBACK)} demo={null} />;
}

export default function Page({ searchParams }: PageProps<"/">): ReactElement {
  // Until the snapshots arrive the page is the loading state: the claim and the form are real.
  return (
    <Suspense fallback={<ClientListScreen view={{ kind: "loading" }} demo={null} />}>
      <Clients searchParams={searchParams} />
    </Suspense>
  );
}
