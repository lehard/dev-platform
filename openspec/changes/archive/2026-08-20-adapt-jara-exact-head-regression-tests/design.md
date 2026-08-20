# Design: reviewed Jara exact-head test compatibility adapter

The adapter is limited to the exact SHA-256 of the known Jara regression test
file. It applies three deterministic replacements that make the strict mocks
return a fixed local head and an exact GitHub PR record, while preserving each
test's original merge/cleanup assertion. A migrated test file is accepted on
rerun only when reversing the known replacements reconstructs the reviewed
legacy bytes; any partial marker, missing replacement, or different source
blocks before a write.

The publication harness and this companion test file are planned completely
before either is written. This makes the change safe for an unmigrated Jara
base and for a known partially-updated rollout branch, without accepting
unknown project-owned drift. The Jara-specific adapter is never selected for
Planner or Cuby.

## Rollout risk and mitigation

Changing a project-owned test file is a cross-repository compatibility action.
Exact legacy and reversible-migrated predicates prevent Dev Platform from
rewriting a downstream edit. Standard rollout creates a reviewed exact-version
PR and only supersedes an older bot-owned rollout after the replacement exists;
it does not auto-merge downstream work.
