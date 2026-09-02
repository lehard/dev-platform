# Verification: systematic bug diagnosis

## Semantic review

Completeness: all 12 OpenSpec tasks are complete. The capability reuses the existing descriptor, project opt-in, materialization, update, removal, and eval lifecycle; it does not add another registry or task state machine.

Correctness: `systematic-bug-diagnosis` requires a directly observed failure condition before a root-cause claim, records only bounded reproducer/probe/regression evidence, requires a valid regression seam or an explicit limitation, and closes by rerunning the original failure condition and removing tagged instrumentation. Its deterministic fixture covers ten diagnosis triggers and ten hard negatives for bounded quick corrections; the representative record rejects a timeout hypothesis before the parser-field repair.

Coherence: the canonical descriptor/instruction, deterministic eval fixture, tests, source documentation, and Copier template use the existing optional-capability conventions. The reviewed upstream is pinned in the capability guidance; no upstream files are vendored.

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review against proposal, delta spec, design, tasks, descriptor/instruction, deterministic fixture, and focused capability/template checks.
Automated-Checks-Evidence: automated-checks.json
