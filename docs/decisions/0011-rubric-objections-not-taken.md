# 0011: six objections to the rubric that were not taken

**Status:** accepted, 2026-11-19 ("as drafted")

**Context.** When the measure was written, a second reader labelled every case independently and, apart from checking the labels, raised objections to the rubric "as a deliverability specialist would". Two were taken and changed `spf_weak_all`. Six were not. I signed the rubric off as drafted; the six are recorded here and named in the limits in [docs/EVALS.md](../EVALS.md).

**Decision.** The rubric stays as drafted on these six points. Each is a known limit of the measure.

1. **Low volume is cut at 1,000 messages a week.** At 1,000 to 3,000 a week, one or two complaints still make 0.10%, so "expected" for `complaint_rate_elevated` just above the cut rests on very few complaints.
2. **Low volume is a seven-day figure but also gates the thirty-day open rate.** One complaint in 410 messages is noise; an open rate over a month of mail is less so. The reason given for the rates does not hold as well for `engagement_declining`.
3. **An open-rate fall is given the same weight as the other signals.** Mail privacy proxying inflates opens. A relative fall is still usable, but a specialist would weight it below complaints and reputation. Some cases expect it alone.
4. **`p=quarantine` with `pct=0` counts as enforcing.** It is a known deliberate setup that in effect is `p=none`, and `pct` is being retired from the protocol. The rubric calls it enforcing, with `dmarc_partial_enforcement` expected.
5. **`volume_spike` and `new_domain_volume` can both be expected for one fact.** A new domain that ramps fast is counted twice.
6. **A DKIM key found in DNS is treated as a key in use.** A key that answers at a selector is not proof that it signs mail. The rubric allows for this only by making a mix of key sizes "acceptable" rather than "expected".

**Consequence.** A model that reasons like a specialist on these points can lose coverage or precision against the labels, and the scores should be read with that in mind. `docs/EVALS.md` names all six under its limits. Revisit any of them if a deliverability specialist reviews the rubric, or if a miss on the paid eval runs traces back to one of them: that would be a change to the measure.
