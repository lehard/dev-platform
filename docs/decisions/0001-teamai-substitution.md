# DEC-0001: TeamAI substitution after the v0.25.0 pilot

- **Status:** Current
- **Scope:** Dev Platform and rendered managed projects; TeamAI as an external agent-infrastructure dependency or substitute
- **Decision date:** 2026-09-28
- **Authored against revision:** `d09c1cc8591e08c2c42ce866d6e2ea6d96e6f2ac`
- **Evidence revision:** `2e7748955d9193cf0fc01245e0d16ca292ea9589` (pilot baseline)
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

Do not adopt TeamAI as a production dependency or wholesale replacement now. Keep the overlapping capabilities Dev Platform-owned until a separately authored, verified adoption change is delivered. Continue monitoring TeamAI and reassess individual capabilities when the triggers below fire. This summarizes the [v0.25.0 substitution evaluation](../engineering/upstream-evaluations/teamai.md); its per-capability decisions and observations remain the detailed evidence.

## Rejected-for-now alternative and rationale

Wholesale adoption on stable `teamai-cli@0.25.0` is rejected for now. The pilot observed that the team repository cannot be pinned to an immutable reviewed revision: a later pull replaced a locally checked-out tag, so managed behavior could change outside a Dev Platform release. A colliding TeamAI skill overwrote a platform-owned agent surface. Installation and rollback ownership were also insufficiently bounded: uninstall removed hooks used by another project and left generated files and local data behind. These conflict with [release and rollout ownership](../release-policy.md) and the [upstream substitution gate](../engineering/upstream-substitution.md). The [pilot evaluation](../engineering/upstream-evaluations/teamai.md) contains the exact scenarios and per-area evidence.

## Deferred and watched candidates

| Capability | Why it remains a candidate | Present decision |
| --- | --- | --- |
| Version-bound or on-demand built-in skills | Could inform pinned, reviewed resource delivery; observed only in 0.26 prerelease research, absent from stable 0.25.0 | Watch |
| Project and team learnings with recall | Cross-task knowledge retrieval solves a different problem from friction intake; the pilot showed retrieval but direct unreviewed publishing and always-apply rules need review | Watch for a bounded pilot |
| Codebase knowledge and wiki | May offer useful extraction and retrieval patterns after provider-free, revision-bound behavior is proven | Watch |
| Session, usage and friction analytics/dashboard | May inform local diagnostics, subject to prompt retention and reporting controls; it does not replace platform process health | Watch as design reference |
| Roles, namespaces and multi-project resource selection | The pilot showed useful partitioning, but the mutable team branch lacks controlled release and rollback | Watch |
| Model profiles | Possible future reference for model configuration; absent from stable 0.25.0 and distinct from the routing gate | Watch |

These candidates may be borrowed as design input or tested independently. None is `adopt-next-step` on the current [per-capability record](../engineering/upstream-evaluations/teamai.md).

## Revisit triggers

Re-evaluate against a **stable** TeamAI release when evidence shows any material change to the blocker or candidate conditions:

1. The team repository and distributed resources can be pinned to reviewed, immutable versions, with changes reaching managed projects only through a Dev Platform release and controlled rollback.
2. TeamAI protects foreign-owned agent surfaces, honors hook opt-out, and provides project-scoped install/uninstall that restores shared settings without affecting other projects.
3. Version-bound/on-demand skills or model profiles graduate from prerelease to stable; provider-free codebase extraction or a reviewable learnings/recall path becomes available.
4. The proposed **Management Backend** becomes an implemented, versioned and reviewed product capability with immutable publication and rollback. The proposal is a future substitution signal, not an implemented production backend today; its relevance is recorded in the originating Requirement.

A trigger starts a new bounded evaluation under the [upstream substitution gate](../engineering/upstream-substitution.md). It does not turn a watched capability into implementation work or change OpenSpec behavior by itself.
