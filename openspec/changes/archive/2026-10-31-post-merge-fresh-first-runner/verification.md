OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the lifecycle-workers delta, proposal, design and tasks; targeted unit tests (test_autonomous_integration_contour, test_github_read_cache, test_post_merge_runner, test_requirement_contribution_composition: 191 passing; test_lifecycle_workers, test_lifecycle_overview: passing); a live read-only measurement of `work-next --dry-run` against lehard/dev-platform; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring with an ADD approved by the owner through the chat coordinator (2026-10-31); thresholds come from the measured baseline.
- Requirements are added, not modified: the existing runner and discovery requirements exceed the 500-character body limit of newer OpenSpec and are split by a separate change; the added ones narrow behavior without contradicting them.
- Early stop applies only when every requested kind is a post-merge kind; other kind sets keep the full scan and ascending order.

## Measurement

- Before (main `f1d36b2a`, 2026-10-31): `work-next --kinds retrospective,terminal-reconciliation,cleanup --dry-run` took 160 s and offered #464 (cProfile: 133 `gh` reads 109 s, 136 read-cache parses 42 s).
- After (this branch, same machine, same GitHub state plus one merge): 8.9 s cold and 6.7 s warm, offering #823 (merged that morning). Threshold "fresh obligation at most 15 s" met. Idle and the day median are observed after delivery from the runner journal.

## Completeness

- Fresh first and early stop: `FreshFirstSelectionTests` (newest merge first without reading older PRs, merge time not number decides, open PRs first, unread stub resolved only when reached, missing resolver named, idle run derives and settles every candidate, missing `merged_at` fails, other kinds ascending).
- Discovery: settled PR in the recent page skipped, lazy label-tail stubs and `resolve_candidate` (`CandidateDiscoveryTests`); existing discovery tests pass.
- Read cache: unchanged file parsed once per process, reloaded and revalidated after another process rewrites it (`test_unchanged_file_is_parsed_once_per_process_and_reloaded_after_a_change`); corrupt-cache cases still fail naming the file.
- Runner: a run started before the deadline gets the claim TTL as timeout and the round ends `max-seconds` without error; a run killed at the claim TTL fails the round (`test_round_budget_bounds_starts_and_a_run_is_bounded_by_the_claim_ttl`, `test_run_killed_at_the_claim_ttl_fails_the_round`); no run starts after the deadline (existing test).
- Composition: the terminal gate checkout gets `contract_from=<integration>/.dev-platform.toml` (`test_terminal_gate_checkout_gets_the_trusted_integration_contract`); the `run_claimed_post_merge` composition checkout uses the same contract.

## Correctness

- No defaults: an unread stub without a resolver, a merged PR without `merged_at`, a missing trusted contract and a corrupt cache all fail explicitly.
- `skipped` semantics unchanged: an unreadable PR is skipped and named; a run with no job and skipped PRs still fails.
- The settled label is still written only for a chain with no next job and no exhausted obligation, so skipping labeled PRs hides no open or spent obligation.
- The cache memo is keyed by inode, mtime and size; writes happen under the existing file lock and refresh the memo with the written content.

## Coherence

- Spec delta, proposal, design, tasks and `docs/engineering/hosted-lifecycle-workers.md` describe the same order, discovery and round budget; the platform manifest is regenerated.

## Not verified / limits

- Not exercised through the installed LaunchAgent; the idle threshold and the day median are confirmed from the journal after merge.
- PR #362 already exhausted its composition terminal attempts on `agent_tools`; it needs `reoffer-post-merge` after merge (coordinator).
