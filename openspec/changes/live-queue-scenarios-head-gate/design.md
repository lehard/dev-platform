## Decisions

- **Executors.** The model is scripted, GitHub is not. Review launches the provider binary, not `--llm-command`, so the scripted reviewer sits behind `DEV_PLATFORM_CLAUDE_BIN`; the worker, its readiness probe and report handling stay real. Each scenario needs a chosen finding or repair, which a real model cannot promise. Real writer and hosted review stay outside coverage and are listed as a limit.
- **Hosted classes.** The sandbox offers finalize and integrate hosted, so hosted finalize runs there. Review runs locally through the scripted executor, so no provider token is stored.
- **Gate placement.** The gate runs at developer handoff on the operator Mac, in `scripts/dogfood_task.py finish`, not in lifecycle preflight: preflight also runs in hosted finalize, which has no receipt. Public CI cannot hold sandbox credentials, and hosted finalize cannot reach operator-only work.
- **Surface.** The paths that need a receipt are declared in `dev-platform/live-scenario-gate.toml` and tested against the queue and lifecycle modules. The receipt binds to those paths at the tested head, so evidence commits keep it and a merge that changes them needs a new run.
- **Blocking.** Missing receipt or new red scenario refuses handoff. A known failure names its defect and does not block.
- **Conflict.** Two tasks on one file stop at the board's scope overlap, so main moves through a direct commit of the runner after admission.
- **Project.** A managed start needs a Backlog Project with the platform statuses, so the runner creates and reconciles the sandbox one here rather than in the Requirement child.
- **Cost.** Duration and Actions use are measured on real runs and documented. A shorter set is defined only from those numbers.

## Risks

Queue deliveries depend on sandbox availability. An unavailable sandbox fails explicitly and is resolved by the coordinator; there is no silent skip.
