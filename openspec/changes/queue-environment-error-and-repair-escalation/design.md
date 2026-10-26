## Context

- `rederive_archived_specs` raises `RederivationFailed` for every failure; `_prepare` turns it into `IntegrationRepairNeeded`, so a runner that lacks a dependency produced an integration-repair job (#730).
- `_regenerate` runs the declared command from the trusted default-branch root with the tree placeholder set to the merged checkout.
- Attention comments exist for `blocked-escalation` (`ensure_attention`, keyed per exact round).

## Decisions

- **Environment is proven, not guessed from stderr.** After a regeneration command fails on the merged tree, the same command runs once over a pristine detached worktree of the fetched main. Main is the integrated, checked state, so a failure there is the runner's environment (or main itself), never the candidate: `RederivationEnvironmentFailed`. Success there keeps the merged-tree failure as integration repair. A missing OpenSpec CLI and an `OSError` starting the command are environment failures directly.
- **The queue run fails, the candidate stays.** `QueueEnvironmentError` is not a candidate defect: no block, no repair job, no state record. The worker continues with other candidates (a plain clean merge does not need the environment) and ends with `environment-error`, which is not a progress state, so the workflow run is red and names each cause. A progress outcome of another candidate in the same run is returned inside that result.
- **Escalation reuses the attention mechanism.** `_transition` posts `ensure_attention` for `repair-pending` and `integration-repair-pending` exactly as for `blocked-escalation`; `attention_body` renders a repair-specific text with the operator command (`lifecycle_workers.py work-next --repo <repo> --kinds <kind> --writer claude-sandboxed --run`). The key per exact round (head, state, red gate, attempts) posts once per round. The job stays published and claimable.

## Risks

- The probe adds one regeneration run only on the failure path.
- A main that is itself broken for the generator is reported as an environment failure; the message names the command and main's head, which is the correct operator action either way.
