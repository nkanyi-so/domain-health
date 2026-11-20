# 0013: the README leads with the finding, then "Run it"

**Status:** decided by the owner, 2026-11-20 (in the session, after merging Phase 2).

**Context.** `docs/profiles/portfolio-piece.md` gives the README a seven-section spine whose first section is "Run it". After the Phase 2 result the owner asked that the README lead with the finding: the eval was built before the prompt, it showed that rules beat the model on this task, and the product ships that way. The two orders clash, and Phase 6 would have had to stop to ask which wins.

**Decision.** The finding comes first, then "Run it", then the rest of the spine in the profile's order. The finding is a short opening, not an eighth section with its own detail: the eval table, the failure and the limits stay in the sections the profile gives them, and the opening links to them.

**Consequence.** Phase 6 builds the README in this order without stopping. The profile file is not edited; where it and this record differ on the README's opening, this record is the owner's later word. The Phase 6 checklist line "the README leads with the finding" is read this way.
