import type { Metadata } from "next";
import { type ReactElement, Suspense } from "react";
import { ClientScreen } from "@/components/client-screen";
import { demoClientPage } from "@/data/demo-states";
import { FALLBACK } from "@/lib/fallback";
import { loadClientPage } from "@/lib/server/data";
import { demoName } from "@/lib/view/demo";
import { clientPageView } from "@/lib/view/screens";

type Props = PageProps<"/clients/[id]">;

/** The twelve seeded clients are known when the page is built. */
export function generateStaticParams(): { id: string }[] {
  return FALLBACK.clients.clients.map((client) => ({ id: client.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const client = FALLBACK.clients.clients.find((entry) => entry.id === id);
  return { title: client ? client.name : "No such client" };
}

async function Client({ params, searchParams }: Props): Promise<ReactElement> {
  const demo = demoName("client", (await searchParams).demo);
  if (demo) {
    return <ClientScreen view={demoClientPage(demo)} demo={demo} />;
  }
  const { id } = await params;
  return <ClientScreen view={clientPageView(await loadClientPage(id), FALLBACK)} demo={null} />;
}

export default function Page({ params, searchParams }: Props): ReactElement {
  return (
    <Suspense fallback={<ClientScreen view={{ kind: "loading" }} demo={null} />}>
      <Client params={params} searchParams={searchParams} />
    </Suspense>
  );
}
