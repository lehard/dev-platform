# DEC-0008: One actor, one entry and one state owner for every lifecycle stage

- **Status:** Current
- **Scope:** The end-to-end task lifecycle from Business Requirement to merge, release and rollout
- **Decision date:** 2026-10-31
- **Authored against revision:** `f1d36b2a29883ecb8ab08e6e9e05f4139f391f86`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

The owner approved the target lifecycle in the [task lifecycle map](../engineering/lifecycle-map.md) (BR-942): every stage has one actor, one entry and one place where its state lives. The developer's work ends at `finish`. Review, finalize and merge run as hosted jobs and the queue, and retrospective, Requirement close and cleanup run as post-merge runner jobs. The coordinator allocates streams, escalates to the owner, starts repair and runs recovery.

The eight accepted choices:

1. **Archive only in finalize.** In the queue path the developer never archives. Finalize checks every archive prerequisite at once, and archive no longer starts a review. In the downstream `light` profile, `finish` calls the same finalize function.
2. **Requirement retrospective and close only in the post-merge runner.** The agent-run "before publication" retrospective and the pre-merge composition retrospective are removed. `advance` ends at "all mandatory children merged".
3. **One `start` entry.** It applies immediately in this repository. Downstream, the old entries are removed in the next MAJOR with no transitional aliases.
4. **One `recover` command** replaces the five recovery tools. The old subcommands are removed in the same release.
5. **The v2 queue record is the only candidate state.** v1 admission comments and `publication:*` labels are removed in a one-time cutover with an empty queue and no compatibility mode. `lifecycle:*` labels are derived from the record.
6. **Routing tiers are R1/R2/R3 everywhere.** `--tier` replaces `--profile routine/standard/complex`.
7. **The coordinator role** covers streams, escalations, repair and `recover`. It does not start review, finalize, merge or post-merge jobs.
8. **Overlapping spec families are merged:** four lifecycle specs into one and three shared-workspace specs into one, after the OpenSpec upgrade (BR-799) completes.

Delivery runs as the small Requirements BR-949 to BR-955, after the post-merge stabilization in BR-939 and BR-924. The documentation rewrite (BR-946) comes last. The order is in the map.

## Rejected and deferred alternatives

- **Archive stays with the developer and leaves finalize:** rejected. It is a smaller change, but it keeps the most fragile step on the developer and preserves the post-finalize dead end.
- **Transitional aliases for the old start entries for one release:** rejected. An alias is a second path, which this decision exists to remove.
- **Compatibility reading of v1 records during the cutover:** rejected under the no-fallback rule. The cutover waits for an empty queue instead.
- **One large simplification change:** rejected. The owner requires small slices with bounded review rounds.

## Evidence

- The 2026-10-31 platform review found the following:
  - archive happens in three places, and missing prerequisites surfaced one at a time (lehard/dev-platform#807);
  - re-handoff after finalize was a dead end (lehard/dev-platform#810);
  - sequential children needed manual re-preparation (lehard/dev-platform#792, lehard/dev-platform#791);
  - a fresh-base refusal followed a full validation run (lehard/dev-platform#818);
  - there are six start entries and five recovery tools, and candidate state is kept in more than ten places;
  - `chat-coordinator.md`, `task-intake.md`, `agent-workflow.md` and `AGENTS.md` disagree on who archives and who runs the Requirement retrospective.
- The post-merge runner journal for the same day showed a median of 220 seconds per job, and 44 of 78 rounds were killed by their time bound.

## Revisit triggers

- A slice cannot keep a stage single-owner without breaking an accepted spec. In that case resolve it through the managed change, not by keeping a second path.
- The `light` profile needs behavior that the shared finalize or post-merge functions cannot provide.
- The post-merge runner cannot meet its throughput requirement (BR-939). Moving retrospective and close to it then needs re-evaluation.
