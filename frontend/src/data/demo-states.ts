// The fixed views behind the `?demo=<name>` flag (docs/DESIGN.md, "The 17 states"). Each is
// built from the bundled seeded snapshots, typed as the API types them, so a screenshot of a
// state is the same on any day. A demo view is only drawn: nothing here is saved or sent.
//
// The four states a seeded client shows by itself use that client's bundled page as it is:
// healthy (Harbourlight Books), fixes only (Fernhollow Garden Supply), risks only (Oakhaven
// Outfitters) and both (Northwind Cycles). The others change one of those pages in a stated way.

import type { ClientPage, LiveCheckResult, Risk } from "@/lib/api-types";
import { FALLBACK } from "@/lib/fallback";
import { afterClick } from "@/lib/view/client-page";
import type { DemoName } from "@/lib/view/demo";
import { addDays } from "@/lib/view/format";
import { type LiveCheckView, refusalMessage } from "@/lib/view/live-check";
import {
  type ClientListView,
  type ClientPageView,
  clientListView,
  snapshotView,
} from "@/lib/view/screens";

/** The day every demo view is dated, so its wording does not move. */
export const DEMO_DAY = "2026-11-20";
/** When the demo's handled clicks were made. */
const CLICKED_AT = new Date(`${DEMO_DAY}T09:00:00Z`);

function bundled(id: string): ClientPage {
  return FALLBACK.snapshots[id];
}

/** A bundled page as a visitor's own, dated the demo day (or the day given). */
function dated(page: ClientPage, day: string = DEMO_DAY): ClientPage {
  const at = `${day}T06:00:00Z`;
  return {
    ...page,
    scope: "sandbox",
    snapshot: { ...page.snapshot, day, started_at: at, finished_at: at },
  };
}

function borrowed(from: string, type: Risk["type"], domain: string): Risk {
  const risk = bundled(from).snapshot.ranked.find((entry) => entry.type === type);
  if (!risk) {
    throw new Error(`the bundled page of ${from} has no ${type} risk`);
  }
  // The ID is built here, as everywhere, from the type and the domain it is shown under.
  return { ...risk, id: `${type}:${domain}` };
}

/**
 * State 6 needs six ranked risks, and no seeded client has more than four on any day. The owner
 * agreed it is shown through this flag only. The view is Oakhaven Outfitters' page with its own
 * two risks followed by four recorded for other seeded clients, so the list is six long; the
 * four borrowed wordings do not describe Oakhaven's figures.
 */
function sixRisks(): ClientPage {
  const page = dated(bundled("oakhaven-outfitters"));
  const { domain } = page.snapshot;
  const ranked: Risk[] = [
    ...page.snapshot.ranked,
    borrowed("willowmere-pets", "spf_near_lookup_limit", domain),
    borrowed("emberglow-events", "engagement_declining", domain),
    borrowed("silverbrook-dental", "bounce_rate_elevated", domain),
    borrowed("silverbrook-dental", "complaint_rate_elevated", domain),
  ];
  return { ...page, snapshot: { ...page.snapshot, ranked, visible: ranked.slice(0, 5) } };
}

function handledOne(): ClientPage {
  const page = sixRisks();
  return afterClick(page, page.snapshot.ranked[0].id, "handled", CLICKED_AT);
}

function allHandled(): ClientPage {
  const page = dated(bundled("oakhaven-outfitters"));
  return page.snapshot.ranked.reduce(
    (seen, risk) => afterClick(seen, risk.id, "handled", CLICKED_AT),
    page,
  );
}

function risksUnavailable(): ClientPage {
  const page = dated(bundled("northwind-cycles"));
  return {
    ...page,
    snapshot: {
      ...page.snapshot,
      risks_status: "unavailable",
      risks_unavailable_reason: "the model's answer did not pass its checks",
      ranked: [],
      visible: [],
      suppressed: [],
    },
  };
}

export function demoClientList(name: DemoName<"list">): ClientListView {
  return name === "loading"
    ? { kind: "loading" }
    : clientListView({ kind: "unreachable" }, FALLBACK);
}

export function demoClientPage(name: DemoName<"client">): ClientPageView {
  switch (name) {
    case "healthy":
      return snapshotView(dated(bundled("harbourlight-books")), { writes: "local" });
    case "fixes-only":
      return snapshotView(dated(bundled("fernhollow-garden")), { writes: "local" });
    case "risks-only":
      return snapshotView(dated(bundled("oakhaven-outfitters")), { writes: "local" });
    case "both":
      return snapshotView(dated(bundled("northwind-cycles")), { writes: "local" });
    case "handled-one":
      return snapshotView(handledOne(), { writes: "local" });
    case "all-handled":
      return snapshotView(allHandled(), { writes: "local" });
    case "risks-unavailable":
      return snapshotView(risksUnavailable(), { writes: "local" });
    case "no-snapshot":
      // Today has none; the day before's is shown in its place, and cannot be marked.
      return snapshotView(dated(bundled("driftwood-coffee"), addDays(DEMO_DAY, -1)), {
        shownInsteadOfToday: true,
        writes: "old-day",
      });
  }
}

/**
 * A check of example.com as the live check answered it on the day this view was written: its SPF
 * and DMARC records as read, and no usable DKIM key at the common selectors.
 */
export const DEMO_RESULT: LiveCheckResult = {
  domain: "example.com",
  checks: {
    domain: "example.com",
    spf: {
      check: {
        present: true,
        record_count: 1,
        valid: true,
        lookup_count: 0,
        all_qualifier: "-all",
      },
      records: ["v=spf1 -all"],
      problems: [],
    },
    dkim: {
      check: { selectors_probed: 12, keys: [] },
      other_keys: [],
      problems: ["every selector probed answers with a revoked (empty) key"],
    },
    dmarc: {
      check: {
        present: true,
        valid: true,
        policy: "reject",
        subdomain_policy: "reject",
        pct: 100,
      },
      record: "v=DMARC1;p=reject;sp=reject;adkim=s;aspf=s",
      found_at: "example.com",
      problems: [],
    },
  },
  fixes: [
    {
      type: "dkim_missing",
      source: "dns",
      instruction:
        "Publish a DKIM key for this domain, or tell us the selector in use: none was found at the common selectors.",
    },
  ],
  checked_at: `${DEMO_DAY}T14:02:00Z`,
  cached: false,
  queries: 14,
};

export function demoLiveCheck(name: DemoName<"check">, typed: string): LiveCheckView {
  switch (name) {
    case "running":
      return { kind: "running", domain: typed };
    case "result":
      return { kind: "result", result: DEMO_RESULT, ageLine: null };
    case "refused":
      return { kind: "refused", domain: typed, message: refusalMessage("ip_address") };
    case "rate-limited":
      return { kind: "rate-limited" };
    case "cap-reached":
      return { kind: "cap-reached" };
  }
}
