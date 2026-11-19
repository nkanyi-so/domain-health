# 0004: Firestore, one snapshot per client per day, transactions, two scopes

**Status:** accepted, 2026-11-19 (intake; the two scopes chosen by the owner)

**Context.** The page reads one document per client per day. Two writers touch it: the daily worker and a person clicking "handled". In the original, a click made while the daily run was writing could be lost, or a handled risk could come back. A public demo adds a second problem: one visitor's clicks must not spoil the page for the next, and the brief also asks for admin auth.

**Decision.** Firestore in Native mode. The snapshot's document ID is the date, so a rerun overwrites. The daily write and the handled / reopen click are each one transaction that reads the handled map and today's snapshot and writes the result; whichever commits second is retried by Firestore against the new state. One pure function computes the visible list for both. The same two functions run in two scopes: the shared state, written only with an admin session, and a per-visitor sandbox keyed by an anonymous signed session, expiring after a day through a TTL policy.

**Consequence.** The race is closed by the database, and a test runs it against the emulator. A visitor can try the loop for real without affecting anyone. The cost: two scopes to test, and the emulator needs a JDK of 21 or later locally and in CI. Free tier: 50,000 reads and 20,000 writes a day, far above twelve clients and a demo's traffic. Firestore's location cannot be changed after creation. Revisit if reads per page view grow enough to matter.
