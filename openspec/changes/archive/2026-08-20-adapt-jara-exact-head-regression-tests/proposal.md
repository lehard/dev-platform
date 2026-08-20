# Proposal: adapt reviewed Jara regression tests with exact-head migration

## Why

The v1.4.35 Jara migration correctly activates exact-head publication before
the CLI guard, but its three known strict subprocess mocks do not model the
new mandatory local-head and exact-PR discovery calls. Jara rollout PR #73 is
therefore safely blocked by CI.

## What changes

- Extend the Jara-only compatibility migration with a reviewed exact-byte
  adapter for `scripts/tests/test_merge_to_main.py`.
- Keep the harness and test transforms deterministic, idempotent and
  fail-closed for any unreviewed drift.
- Release a patch and let normal managed rollout create a replacement Jara PR;
  do not alter Planner or Cuby rollout PRs.

## Non-goals

- Do not manually edit, merge, or force-push Jara rollout PR #73.
- Do not alter Planner #46 or Cuby #57.
