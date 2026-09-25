# Verification: private-lineage-public-boundary

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of the authored outcome, both specification deltas, completeness, correctness and coherence against the implementation; targeted Git-backed tests; full platform validation; current-tree privacy scan; bounded live audit of editable public GitHub surfaces.

Automated-Checks-Evidence: automated-checks.json

Requirement-Integration-Exception: This private Requirement has exactly one technical child, so a multi-child integration candidate cannot be assembled; publish this verified child through its exact managed PR and reconcile the parent after terminal delivery.

## Outcome and evidence

- Public managed provenance, checkout check evidence and new Requirement integration candidates use non-derivable lineage handles. The exact Issue identity remains in ignored local state and is proven by a mapping comment on the same private Issue. Missing or conflicting mapping blocks recovery or publication.
- Current tracked archived provenance, check receipts, selected verification prose and the historical integration manifest were redacted. Redaction markers identify edits made after the original verification; original check outcomes were retained. Old published Git commits were not rewritten and remain the accepted residual risk.
- The current-tree guard passes and is installed in protected CI, the managed finish path and the PR publisher before push. It detects supported direct private Issue forms in candidate files, branch and new commit messages, and proposed PR text; it does not claim to detect arbitrary prose.
- A bounded live audit removed four confirmed affected public Actions runs. Of 177 listed public runs, logs from 172 were accessible and scanned; three other runs did not return logs and remain unverified. Editable public Issue/PR text with confirmed direct references was sanitized. No second public report or storage destination was added.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 -m ruff check template/scripts scripts tests`: passed.
- `python3 scripts/managed_projects.py validate`: passed, three managed projects.
- `python3 scripts/run_test_groups.py --all`: passed, all 13 groups and 1312 discovered tests before two final targeted integration tests were added. The archive helper will rerun the selected full checks on the final candidate and record the exact result in `automated-checks.json`.
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `openspec validate private-lineage-public-boundary --strict --no-interactive`: passed.
- `python3 -m pytest -q tests/test_requirement_integration.py::RequirementIntegrationTests::test_private_compose_uses_opaque_branch_commits_and_manifest tests/test_requirement_integration.py::RequirementIntegrationTests::test_private_manifest_projection_fails_without_authorized_mapping`: both passed.
- `python3 scripts/check_private_backlog_refs.py` and `git diff --check`: passed.

## Semantic OpenSpec review

- **Outcome:** Exact private lineage is absent from current candidate records while an authorized private Issue read still proves the mapping. The one-child independent publication exception is explicit above.
- **Completeness:** Managed import, active/archived evidence, Requirement assembly and merge recovery, process-evidence comments, public guard, historical current-tree migration, and editable external surfaces were checked. The private combined report remains in the private Backlog.
- **Correctness:** Opaque handles are random and bound to one configured private Issue and change. The publisher compares committed public projection with the exact private manifest and checks parent/child links before push. Git-backed tests cover branch, commit and manifest projection; fail-closed mapping and direct-reference detection are tested.
- **Coherence:** The proposal, design, specification deltas and implementation agree on current-tree cleanup and prevention of supported new leaks. No claim is made that historical Git commits or three unavailable old logs are clean.

The automated-checks marker names evidence the archive helper will generate; it does not assert that this file existed before archive.

## Post-archive CI correction

The first protected PR check found an owner/project reference in the current public snapshot. The workflow now reads the private Backlog repository from an Actions variable, the one-time migration program was removed after use, and guard tests use a fictional repository. The repository variable was set before retrying publication. `python3 tests/public_distribution_snapshot_smoke.py` then passed on a freshly extracted snapshot, including all 13 test groups and 1317 discovered tests plus OpenSpec lifecycle hygiene. The original automated archive receipt remains an accurate record of the earlier archived candidate; this section records the subsequent correction separately.
