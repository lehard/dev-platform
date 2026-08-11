# Managed rollout stale-PR reconciliation evidence

Date: 2026-08-11

The implementation was merged through protected `main` in [PR #86](https://github.com/lehard/dev-platform/pull/86), followed by the maintenance-authority correction in [PR #87](https://github.com/lehard/dev-platform/pull/87). Both Platform CI runs passed before merge.

## Reviewed dry-run

[Run 31463657179](https://github.com/lehard/dev-platform/actions/runs/31463657179) completed successfully with no cross-repository mutation. Its per-target `rollout-supersession-*-dry-run-31463657179` artifacts contained this exact closure plan:

- `lehard/Jara_Fin`: close rollout PRs [#25](https://github.com/lehard/Jara_Fin/pull/25), [#26](https://github.com/lehard/Jara_Fin/pull/26), and [#27](https://github.com/lehard/Jara_Fin/pull/27), because committed `main` already records `v1.4.20`.
- `lehard/planner-agent-lab`: close [#31](https://github.com/lehard/planner-agent-lab/pull/31), [#32](https://github.com/lehard/planner-agent-lab/pull/32), and [#33](https://github.com/lehard/planner-agent-lab/pull/33), superseded by the validated newest rollout [#34](https://github.com/lehard/planner-agent-lab/pull/34) for `v1.4.20`.
- `lehard/cuby`: no eligible open rollout PRs and no planned mutation.

No candidate or excluded registry entry appeared in the matrix or artifact set.

## Applied result

[Run 31463725473](https://github.com/lehard/dev-platform/actions/runs/31463725473) completed successfully with `mode=apply` and the explicit confirmation token. Its per-target apply artifacts reproduce the reviewed plan above.

Post-apply API inspection confirmed:

- Jara_Fin has no open `dev-platform/rollout-v*` PR.
- Planner Agent Lab has exactly one open rollout PR: [#34](https://github.com/lehard/planner-agent-lab/pull/34), `dev-platform/rollout-v1.4.20`.
- Cuby remains unchanged.

The closed PRs are annotated with their committed-base or replacement reason. Branch deletion was attempted only after each close confirmation; no deletion warning was emitted by the successful apply run.
