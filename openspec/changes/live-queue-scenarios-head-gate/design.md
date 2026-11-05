## Decisions

- **Executors.** The model is scripted, GitHub is not. Each scenario needs a chosen finding or repair, which a real model cannot promise. Real writer and hosted review stay outside coverage and are listed as a limit.
- **Hosted classes.** The sandbox offers finalize and integrate hosted, so hosted finalize runs there. Review runs locally through the scripted executor, so no provider token is stored.
- **Gate placement.** The gate runs at developer handoff on the operator Mac. Public CI cannot hold sandbox credentials, and hosted finalize cannot reach operator-only work.
- **Surface.** The paths that need a receipt are declared in one place and tested against the queue and lifecycle modules.
- **Blocking.** Missing receipt or new red scenario refuses handoff. A known failure names its defect and does not block.
- **Cost.** Duration and Actions use are measured on real runs and documented. A shorter set is defined only from those numbers.

## Risks

Queue deliveries depend on sandbox availability. An unavailable sandbox fails explicitly and is resolved by the coordinator; there is no silent skip.
