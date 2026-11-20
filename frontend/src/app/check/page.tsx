import type { Metadata } from "next";
import { type ReactElement, Suspense } from "react";
import { FallbackStrip, PageFrame } from "@/components/chrome";
import { LiveCheck, type LiveCheckMode } from "@/components/live-check";
import { demoLiveCheck } from "@/data/demo-states";
import { FALLBACK } from "@/lib/fallback";
import { backendReachable } from "@/lib/server/data";
import { demoName, firstValue } from "@/lib/view/demo";
import type { LiveCheckView } from "@/lib/view/live-check";

export const metadata: Metadata = { title: "Check a domain" };

interface ScreenProps {
  domain: string;
  mode: LiveCheckMode;
  demo: string | null;
  demoView?: LiveCheckView;
}

function Screen({ domain, mode, demo, demoView }: ScreenProps): ReactElement {
  return (
    <PageFrame
      strip={mode === "off" ? <FallbackStrip day={FALLBACK.generated_for_day} /> : null}
      demo={demo}
    >
      <h1 className="t-title">Check a domain</h1>
      <p className="measure mt-2 mb-6">
        Type any public domain. This runs real DNS lookups for SPF, DKIM and DMARC and lists what to
        fix.
      </p>
      {/* Keyed, so a new address starts a new check. */}
      <LiveCheck
        key={`${mode}-${demo ?? ""}-${domain}`}
        initialDomain={domain}
        mode={mode}
        demoView={demoView}
      />
    </PageFrame>
  );
}

async function Check({
  searchParams,
}: Pick<PageProps<"/check">, "searchParams">): Promise<ReactElement> {
  const query = await searchParams;
  const domain = (firstValue(query.domain) ?? "").trim().slice(0, 300);
  const demo = demoName("check", query.demo);
  if (demo) {
    return (
      <Screen domain={domain} mode="demo" demo={demo} demoView={demoLiveCheck(demo, domain)} />
    );
  }
  // Opening the page only asks whether the backend is there. The check itself is a POST made
  // only when the visitor presses "Check domain".
  const reachable = await backendReachable();
  return <Screen domain={domain} mode={reachable ? "live" : "off"} demo={null} />;
}

export default function Page({ searchParams }: PageProps<"/check">): ReactElement {
  return (
    <Suspense fallback={<Screen domain="" mode="live" demo={null} />}>
      <Check searchParams={searchParams} />
    </Suspense>
  );
}
