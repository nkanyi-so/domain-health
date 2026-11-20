import type { Metadata } from "next";
import Link from "next/link";
import type { ReactElement, ReactNode } from "react";
import { PageFrame, ServiceStrip } from "@/components/chrome";
import { ClaimBlock } from "@/components/claim-block";
import { SeededTag } from "@/components/parts";

export const metadata: Metadata = { title: "About this demo" };

function Block({ heading, children }: { heading: string; children: ReactNode }): ReactElement {
  return (
    <section className="measure">
      <h2 className="t-heading">{heading}</h2>
      <p className="mt-2">{children}</p>
    </section>
  );
}

export default function Page(): ReactElement {
  return (
    <PageFrame strip={<ServiceStrip />}>
      <div className="flex flex-col gap-8">
        <h1 className="t-title">About this demo</h1>
        <ClaimBlock />
        <Block heading="What is real">
          The DNS checks. Type any public domain and the page looks up its SPF, DKIM and DMARC
          records and lists what to fix.
        </Block>
        <Block heading="What is seeded">
          The twelve clients, their reputation grades, blocklist status and sending figures. Those
          come from accounts this demo does not have, so they are made up. The clients&apos; DNS
          answers come from fixed zone files. Everything seeded carries this tag: <SeededTag />.
        </Block>
        <Block heading="What the model does here">
          For each seeded client, a model picked risks from a fixed list. What you see was recorded
          from real model runs and is replayed. Nothing is generated on your visit, and a typed
          domain gets no model output at all. The risks are advisory: on this project&apos;s evals,
          rules did better.{" "}
          <Link href="/evals" className="link">
            See the eval result
          </Link>
        </Block>
        <Block heading="Marking a risk handled">
          Marking a risk handled hides it for thirty days. Your ticks are yours alone and reset a
          day after your first one. Other visitors do not see them.
        </Block>
        <Block heading="What this rebuilds">
          A deliverability monitor built for a client&apos;s internal platform, rebuilt in public on
          invented data.
        </Block>
      </div>
    </PageFrame>
  );
}
