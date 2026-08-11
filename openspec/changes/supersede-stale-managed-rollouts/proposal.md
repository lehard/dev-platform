# Change: Supersede stale managed rollout pull requests deterministically

## Why

Managed rollout uses one deterministic branch per platform version and intentionally stops at a reviewable downstream PR. During rapid platform iteration, older rollout PRs can remain open after a newer platform version has already been proposed or even adopted. Jara_Fin and Planner Agent Lab currently demonstrate this accumulation pattern: multiple open `dev-platform/rollout-vX.Y.Z` PRs can coexist even though only the newest relevant platform target should remain actionable.

This is operational debt and a safety ambiguity. Agents and humans must not have to infer which update PR is current, and an old rollout PR should not remain a plausible merge candidate after the downstream base has advanced beyond its target. The cleanup must remain narrowly scoped to rollout-owned branches and managed repositories; it must never close unrelated project PRs or newer rollout work.

## What changes

- Treat the reserved `dev-platform/rollout-vX.Y.Z` head form plus managed-rollout ownership metadata as the canonical identity of a rollout PR. Do not classify PRs from title text alone.
- During a successful rollout preparation for target `vN`, enumerate open rollout PRs for the same managed repository and compare their SemVer targets.
- After the target `vN` PR has been successfully created/reused (or the downstream default branch is already at/above `vN`), close open rollout PRs with target versions lower than the current authoritative target as `superseded`.
- Never auto-close a rollout PR targeting a version newer than the current rollout request. Never touch non-rollout branches/PRs.
- If the new target preparation fails before a replacement PR exists, keep the older pending rollout PRs untouched; cleanup must not destroy the last reviewable update path because a newer attempt failed.
- Delete superseded rollout branches only after their PR is closed, and treat branch deletion as post-close cleanup. A cleanup failure is surfaced but must not reopen or redefine a successfully prepared newer rollout.
- Add a one-time reconciliation/maintenance path that safely closes already-stale rollout PRs across the current `managed-projects.json` allowlist.
- Make stale-version state visible to downstream review: if the downstream base already records a platform version equal to or newer than a rollout PR's target, the rollout helper/diagnostic SHALL classify that PR as stale rather than current.

## Scope

This affects existing managed-project rollout orchestration and future rollout PRs. Fresh project rendering is unchanged except for any reusable rollout-status helper that may be delivered as platform tooling. Cross-repository writes remain restricted to repositories whose registry state is `managed`.

## Compatibility risks

- Incorrect PR identification could close unrelated work; matching must require the reserved rollout branch/version contract and expected rollout ownership.
- Cleanup ordering matters: stale PRs are closed only after a newer target is safely available or the base has already advanced beyond them.
- Repositories may have manually modified rollout branches; supersession closes the stale PR but must not force-push or rewrite branch history.

## Success criteria

For each managed repository there is at most one actionable rollout PR for the newest relevant platform target. Older rollout PRs are deterministically marked/closed as superseded without touching newer or unrelated PRs. A failed newer rollout does not erase the last valid pending update, and stale rollout cleanup never requires force-push or branch-protection bypass.