# Labelling rubric

This is the rule every eval label is read against. It defines the two closed lists (fix types and risk types), the line between them, and for each risk type when a deliverability specialist would flag it (`expected`), when including it is not wrong (`acceptable`), and when flagging it would be wrong or damaging (`wrong`). A risk type that is none of the three for a case is noise: it costs precision and is not counted as harmful.

It belongs to the owner. The build drafted it in Phase 0; the owner signs it off by merging that phase, and changes it by hand after that. A test keeps the lists here equal to the lists in `backend/src/domain_health/types.py`.

Where the labels come from, said plainly: they were drafted by AI against this rubric and against public deliverability guidance, and reviewed by the engineer who built the original system. They were not written or reviewed by a deliverability specialist.

There are two sets of cases. In a **table** case the label is exactly what the bands below give, and a test re-derives it from this file read as a table (`backend/src/domain_health/evals/table.py`). In an **open** case the bands do not settle the matter, and the label is a written call: see "Open cases" at the end.

## The input

Each case's `input` is exactly what the model receives for one client on one day:

- `domain`: the sending domain.
- `checks.spf`: `present`, `record_count`, `valid`, `lookup_count` (DNS lookups the record costs; the limit is 10), `all_qualifier` (`-all`, `~all`, `?all`, `+all`, or null when the record has no `all`).
- `checks.dkim`: `selectors_probed`, and `keys`: each selector found, with `key_bits`.
- `checks.dmarc`: `present`, `valid`, `policy`, `subdomain_policy` (null when the record sets none, so subdomains inherit `policy`), `pct` (100 when a valid record sets none, which is the protocol's default).
- `sources` (seeded on the demo): `reputation.grade` and `reputation.previous_grade` (`high`, `medium`, `low`, `bad`, best to worst), `complaint_rate_pct` and `bounce_rate_pct` (over the last seven days), `volume_7d` and `volume_prev_7d` (messages sent in the last seven days and the seven before), `open_rate_pct` and `open_rate_prev_pct` (the last thirty days and the thirty before; the previous value is null for a domain under 60 days old, which has no such window), `blocklist`, `domain_age_days`.
- `sources.blocklist`: `listed` (on a blocklist now), `listings_90d` (listings that were active at any time in the last 90 days, a current one included), `days_since_delisted` (days since the most recent ended listing came to an end; null while listed now, and null when no listing ended in the last 90 days).
- `fixes`: the fix list the rules already produced from the same data. Each has a `type`, a `source` (`dns` or `seeded`) and an `instruction` in plain words.

Words used below:

- **Enforcing DMARC**: a valid record with policy `quarantine` or `reject`.
- **Low volume**: `volume_7d` under 1,000. A handful of messages moves any rate at that size.
- **A readable SPF record**: exactly one record, and it parses. A record over the lookup limit is still readable: its `all` can be judged, its lookup count is a fix.
- **Volume ratio**: `volume_7d` divided by `volume_prev_7d`. When the previous week is 0 and this week is not, the ratio counts as 2.0 or more.
- **Open-rate fall**: (`open_rate_prev_pct` minus `open_rate_pct`) divided by `open_rate_prev_pct`. There is no fall to read when the previous value is null or 0.

## The line between a fix and a risk

A **fix** is a fault with one correct action. It is read off the data with no judgment, it is true or false whatever else is going on, and a rule produces it. A **risk** is a state that works today, or a trend, that a specialist may or may not raise depending on the rest of the picture. The model ranks risks; it never produces, repeats or contradicts a fix.

Three consequences for labelling:

1. Where a value has crossed into a fix, the risk type on the same signal is `wrong`. Flagging "complaints are elevated" when they are over the limit understates a fault the fix list already carries. The same holds for a blocklist listing, an SPF record over the lookup limit, and a missing or invalid record.
2. A risk type that judges a record is `wrong` when that record is missing or cannot be read: there is nothing to judge until the fix is done. This comes before the type's own lines. It applies to the record the type is about, not to a record it only takes into account: `spf_weak_all` is about the SPF record and merely looks at DMARC.
3. An open fix does not silence the other risks. A domain with a missing SPF record can also have an engagement problem, and the client should hear about both, even where one may be causing the other.

Within one type the lines are read in this order: `wrong` first, then `expected`, then `acceptable`. The first that fits decides. Where none fits, the type is noise for that case; the gaps between the bands below are deliberate.

## Fix types

| Type | Source | True when | The one action |
|---|---|---|---|
| `spf_missing` | dns | No SPF record. | Publish one. |
| `spf_multiple` | dns | More than one SPF record. | Merge them into one. |
| `spf_invalid` | dns | One record that does not parse. | Correct the syntax. |
| `spf_too_many_lookups` | dns | `lookup_count` is 11 or more. | Flatten or remove includes to get to 10 or fewer. |
| `spf_plus_all` | dns | The record ends in `+all`. | Replace it with `~all` or `-all`. |
| `dkim_missing` | dns | No key at any probed selector. | Publish a key, or tell us the selector in use. |
| `dkim_weak_key` | dns | Any key shorter than 1,024 bits. | Rotate to a 2,048-bit key. |
| `dmarc_missing` | dns | No DMARC record. | Publish one, starting at `p=none`. |
| `dmarc_invalid` | dns | A record that does not parse. | Correct the syntax. |
| `blocklist_listed` | seeded | `blocklist.listed` is true. | Fix the cause and request delisting. |
| `complaint_rate_over_limit` | seeded | `complaint_rate_pct` is 0.30 or more. | Stop the offending stream and clean the list. |
| `bounce_rate_over_limit` | seeded | `bounce_rate_pct` is 5.0 or more. | Stop sending to the list and validate it. |

## Risk types

### `dmarc_policy_none`

DMARC is published with `p=none`: reports only, no protection against spoofing.

- **Expected:** policy `none` on a domain at least 90 days old with no SPF or DKIM fix open. Nothing stands in the way of tightening it.
- **Acceptable:** policy `none` on a domain under 90 days old (a monitoring period is the right first step), or while any SPF or DKIM fix is open (the authentication records should be right before the policy moves).
- **Wrong:** DMARC is missing or invalid (that is a fix), or the policy is `quarantine` or `reject`.

### `dmarc_partial_enforcement`

DMARC enforces, but not for all mail or not for subdomains.

- **Expected:** enforcing DMARC with `pct` under 100, or with `subdomain_policy` `none`.
- **Acceptable:** policy `reject` with `subdomain_policy` `quarantine` and `pct` 100: a softer stance on subdomains that is still enforcement.
- **Wrong:** DMARC missing or invalid; policy `none` (`pct` means nothing there); or full enforcement, meaning `pct` 100 with no subdomain policy or one at least as strict as the policy.

### `spf_near_lookup_limit`

The SPF record is valid but close to the limit of 10 DNS lookups, so one provider's change to an include can break it.

- **Expected:** `lookup_count` of 9 or 10.
- **Acceptable:** `lookup_count` of 8.
- **Wrong:** `lookup_count` of 11 or more (that is a fix), 5 or fewer, or an SPF record that is missing, multiple or invalid.

Six and seven are neither: not worth a place in the list, not wrong.

### `spf_weak_all`

The SPF record does not tell receivers to reject other senders.

- **Expected:** a readable record whose `all_qualifier` is `?all` or null, while DMARC is not enforcing. Nothing anywhere tells receivers to refuse other senders.
- **Acceptable:** `~all`, whatever DMARC says: receivers treat a soft fail much like a hard one, and many senders choose it on purpose because `-all` can reject forwarded mail before DKIM is looked at. Also `?all` or null with enforcing DMARC, where DMARC does the refusing. Mentioning either is defensible; expecting it is not.
- **Wrong:** `-all`; `+all` (that is a fix); or an SPF record that is missing, multiple or invalid.

### `dkim_key_1024`

DKIM signs with a 1,024-bit key: valid today, below current practice, due for rotation.

- **Expected:** every key found is at least 1,024 and under 2,048 bits.
- **Acceptable:** a mix: at least one key of 2,048 bits or more and at least one under it. Usually an old selector left in DNS.
- **Wrong:** every key is 2,048 bits or more; no key was found (a fix); or any key is under 1,024 bits (a fix), whatever the other keys are.

### `reputation_declining`

The mailbox-provider reputation grade has dropped since the previous reading.

- **Expected:** `grade` is worse than `previous_grade`.
- **Wrong:** `grade` is the same as or better than `previous_grade`. A recovering domain flagged as declining sends the client looking for a problem that is ending.

### `reputation_poor`

The reputation grade is poor, whichever way it is moving.

- **Expected:** `grade` is `low` or `bad`.
- **Acceptable:** `grade` is `medium`.
- **Wrong:** `grade` is `high`.

### `complaint_rate_elevated`

Complaints are under the hard limit but above what mailbox providers ask senders to stay below.

- **Expected:** `complaint_rate_pct` from 0.10 up to but not including 0.30, and not low volume.
- **Acceptable:** from 0.08 up to but not including 0.10; or from 0.10 up to 0.30 at low volume, where one complaint can produce the rate.
- **Wrong:** 0.30 or more (that is a fix), or under 0.05.

### `bounce_rate_elevated`

Bounces are under the hard limit but high enough to point at list quality.

- **Expected:** `bounce_rate_pct` from 2.0 up to but not including 5.0, and not low volume.
- **Acceptable:** from 1.5 up to but not including 2.0; or from 2.0 up to 5.0 at low volume.
- **Wrong:** 5.0 or more (that is a fix), or under 1.0.

### `volume_spike`

Sending volume jumped week on week. Whether that is a risk depends on whether the domain's standing can absorb it.

- **Expected:** volume ratio of 2.0 or more, on a domain that is either under 365 days old or has a `grade` that is not `high`.
- **Acceptable:** ratio of 2.0 or more on a domain at least 365 days old with `grade` `high` (a seasonal campaign from an established sender); or a ratio from 1.5 up to but not including 2.0 on any domain.
- **Wrong:** ratio under 1.2.

### `new_domain_volume`

A new domain is sending real volume before it has a history: a warm-up risk.

- **Expected:** `domain_age_days` under 30 and `volume_7d` over 5,000.
- **Acceptable:** under 30 days with `volume_7d` of 5,000 or less; or from 30 up to but not including 90 days with `volume_7d` over 5,000.
- **Wrong:** 180 days or older.

### `engagement_declining`

Open rate has fallen against the previous thirty days, an early sign that mail is landing in spam or the list is tiring.

- **Expected:** open-rate fall of 0.20 or more, and not low volume.
- **Acceptable:** a fall from 0.10 up to but not including 0.20; or 0.20 or more at low volume.
- **Wrong:** a fall under 0.05, which includes a flat or rising open rate.

With no previous value, or a previous value of 0, there is nothing to compare, and the type is noise.

### `blocklist_recent`

The domain is not listed now but was recently, or keeps being listed: the cause may not be fixed.

- **Expected:** not listed now, and either `days_since_delisted` is 30 or less or `listings_90d` is 2 or more.
- **Acceptable:** not listed now, exactly one listing in 90 days, and it ended more than 30 days ago.
- **Wrong:** listed now (that is a fix), or no listing in 90 days.

## How a case is labelled

For each of the thirteen risk types, read the case's input against the three lines above and put the type in `expected`, `acceptable`, `wrong`, or none of them. That is a table case, and its `set` is `table`. The `note` says in a sentence or two what the case is there to test. A note that starts with `Hard:` marks a case built to be hard: signals that conflict, a value at or next to a threshold, or a healthy domain that looks odd.

The order of the model's list is not labelled or scored. Coverage, precision and stability look at the set of the first five risks returned, so no case expects more than five. Harmful looks at everything returned, up to eight.

## Open cases

The bands above are thresholds on single fields, with a few fixed conditions on other fields. Anything they decide, a table could decide without a model. A specialist does not read a domain that way: the same number means different things beside different facts, and the bands cannot hold every combination.

An open case is an input where reading the whole picture gives a different answer from the bands for at least one risk type: something the bands expect that a specialist would not insist on here, something they call acceptable, noise or even wrong that a specialist would raise, or something they allow that would be wrong to say to this client. One limit holds for every open case, and a test checks it: a type the bands expect stays expected or acceptable. Its `set` is `open`, and its label differs from the bands' label somewhere; a test checks that it does.

How an open case is labelled:

- The fix list still follows the fix table exactly. Fixes are never a judgment.
- Each of the thirteen types goes in `expected`, `acceptable`, `wrong` or none, as before. Where the call follows the bands, nothing more is needed. Where it departs from them, the `note` gives the reason in plain words and, where one applies, the public guidance it rests on.
- The `note` starts with `Open:` and names, in backticks, every risk type whose placement differs from the bands'.
- The three consequences under "The line between a fix and a risk" still hold: an open call never contradicts or repeats a fix.

Open cases are held out of prompt work. A prompt is written and changed by an agent with fresh context that is given this rubric and the table cases only; it does not read the open cases, their notes or their per-case results. Only their totals are reported, beside a rules-only baseline (the bands, applied by code). The baseline does not score full marks on them, and no version of it that also returns the bands' "acceptable" types does better than the baseline by the spec's rule; tests keep both true. A version with one threshold moved does, so doing better than the baseline is not proof of judgment (decision 0012). Whether the model does better there is reported as evidence, whichever way it comes out.
