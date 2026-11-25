# 0005: backend on Cloud Run with Scheduler and Tasks, guarded; frontend on Vercel with a bundled fallback

**Status:** accepted, 2026-11-19

**Context.** The per-client fan-out (Cloud Scheduler to a dispatch endpoint to one Cloud Task per client) and the transactional snapshot are part of the claim, so the backend belongs on Google Cloud. The other two demos rejected Cloud Run because it "needs a billing account and has no hard cap: budgets only alert". That is still true. A portfolio demo should have nothing that can pause or expire.

Free-tier limits read on 2026-11-19 from Google's free-tier page: Cloud Run 2 million requests, 360,000 GB-seconds and 180,000 vCPU-seconds a month; Firestore 1 GiB, 50,000 reads and 20,000 writes a day; Secret Manager six active versions; Cloud Build 2,500 build-minutes; Artifact Registry 0.5 GB. A billing account is required. Cloud Scheduler (three free jobs per billing account) and Cloud Tasks (a million free operations a month) are from memory, not re-read; both pricing pages are checked before the first deploy.

**Decision.** Cloud Run in `us-central1`, at most one instance, none when idle, request-based billing; Cloud Scheduler once a day; Cloud Tasks with a rate limit and five attempts; Firestore. Guards against spend: the instance limit, no model key in production, a per-address limit and a daily cap on the only public path that does work, counters in Firestore, a $5 monthly budget alert, and an image clean-up policy. Frontend on Vercel Hobby like the other two, deployed from `main`. The frontend bundles the seeded clients' snapshots and serves them with a notice if the backend cannot be reached.

**Consequence.** Expected cost is zero to a few cents a month. The budget only alerts; what bounds spend is that nothing public can make the service do paid work at scale. If the billing account lapses, the backend stops; the page still loads from the fallback and says so, and the live check shows as unavailable. A hard cap (a budget notification that switches billing off) was considered and left out: it would take the demo down to save cents. Revisit if a month's bill passes $1.
