## Decisions

- **Derived, not stored.** The refresh is derived from a trusted terminal receipt, like every post-merge obligation. The refresh key is a digest of the unlinked event ids, so the same set is offered once and a newer set gets a new key.
- **Job identity.** The key is part of the job id. Earlier receipts therefore cannot satisfy the refreshed obligation, and stale results are discarded as before.
- **Order.** Only retrospective and terminal are re-offered. Cleanup stays after terminal. Other blocked terminal outcomes keep their existing budget.
- **Bound.** Refreshes per candidate are limited by `MAX_RETROSPECTIVE_REFRESHES`; past it the obligation stays blocked and is reported.
