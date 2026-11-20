// The seeded figures on a client's page: a label and a value in words, with the previous
// reading where there is one. No colour and no judgement: whether a figure is a problem is the
// fix list's job.

import type { Sources } from "../api-types";
import { formatCount, formatPercent, plural } from "./format";

export interface Figure {
  label: string;
  value: string;
}

function blocklist(sources: Sources): string {
  const { listed, listings_90d, days_since_delisted } = sources.blocklist;
  const first = `${listed ? "Listed" : "Not listed"}. ${plural(listings_90d, "listing", "listings")} in 90 days`;
  return days_since_delisted === null
    ? first
    : `${first}. Delisted ${plural(days_since_delisted, "day", "days")} ago`;
}

export function figures(sources: Sources): Figure[] {
  const openRate =
    sources.open_rate_prev_pct === null
      ? formatPercent(sources.open_rate_pct)
      : `${formatPercent(sources.open_rate_pct)}, was ${formatPercent(sources.open_rate_prev_pct)}`;
  return [
    {
      label: "Reputation",
      value: `${sources.reputation.grade}, was ${sources.reputation.previous_grade}`,
    },
    { label: "Complaint rate", value: formatPercent(sources.complaint_rate_pct) },
    { label: "Bounce rate", value: formatPercent(sources.bounce_rate_pct) },
    {
      label: "Weekly volume",
      value: `${formatCount(sources.volume_7d)}, was ${formatCount(sources.volume_prev_7d)}`,
    },
    { label: "Open rate", value: openRate },
    { label: "Blocklist", value: blocklist(sources) },
    { label: "Domain age", value: plural(sources.domain_age_days, "day", "days") },
  ];
}
