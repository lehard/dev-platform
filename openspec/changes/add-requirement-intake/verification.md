# Verification: Human-facing Business Requirement object

## Method

`/opsx:verify` was not available in this execution environment (no OpenSpec-provided Claude/Codex skill registered in this session). Performed the documented equivalent manual OpenSpec semantic review: re-read `proposal.md`'s Why/What Changes/Success Evidence, `design.md`'s Requirement representation/entrypoint surface/aggregation rules, and the `agent-workflow` spec delta's four ADDED requirements with their scenarios, then checked the implementation (`template/scripts/requirement_intake.py`) and its tests (`tests/test_requirement_intake.py`) against each one individually.

## Outcome / success evidence review

- "A business requirement can be recorded as one Requirement Issue with no OpenSpec artifact" — `create_requirement()` renders only the business-language body (Outcome/Context/Acceptance evidence/Target repository/Exclusions) and creates one labeled Issue; it never touches `managed_task.py`'s OpenSpec authoring path. Covered by `CreateRequirementTests`.
- "`orchestrate_pre_authoring.py` can resume pre-authoring from it" — `start_pre_authoring()` extracts `## Outcome`/`## Target repository` from the Issue body and calls `orchestrate_pre_authoring.init()` directly (the same function #129 already tested for resumability); `test_start_bridges_a_requirement_issue_into_orchestrator_init` confirms the resulting `add.json` carries the parsed target repository and the requirement text lands in the pre-authoring directory unchanged.
- "a handoff-ready intent's resulting internal managed OpenSpec Issue links back to its Requirement and is labeled distinctly from it" — `link_child()` inserts the child reference into the parent's children block, labels the child `type:internal-change`, and appends a `Requirement: owner/repo#N` back-reference; `LinkChildTests` covers both the initial link and its idempotent no-op re-run.
- "`aggregate` reports a Requirement's status derived only from its children's real lifecycle state" — `aggregate()` calls only `managed_project_status.observe()` per child (the same read path #129's dependency, `managed_project_status.py`, already owns) and never writes a status anywhere; `AggregateTests` covers no-children, all-Done, any-Blocked, mixed-in-progress, and an unreadable child failing closed to `unknown` rather than being assumed done or in progress.
- "existing quick-task and direct managed-task/OpenSpec paths are unchanged" — no existing module (`managed_task.py`, `add_intents.py`, `project_evidence.py`, `orchestrate_pre_authoring.py`) was modified in its behavior; `requirement_intake.py` only imports and composes their existing public functions.

## Spec-delta scenario review (`specs/agent-workflow/spec.md` in this change)

- "Requirement authored without OpenSpec" — `CreateRequirementTests.test_create_issues_gh_issue_create_with_the_requirement_label`.
- "Requirement bridges into pre-authoring" — `StartPreAuthoringTests.test_start_bridges_a_requirement_issue_into_orchestrator_init`.
- "A ready intent produces a linked internal change" — `LinkChildTests.test_link_child_inserts_reference_and_labels_and_back_references`.
- "One Requirement produces multiple internal changes" — `link_child()` is called once per child and each call only appends to the children block (verified structurally by the idempotency test not clobbering an existing entry); a dedicated multi-child fixture is exercised in `AggregateTests` (two children per test).
- "Aggregate reflects real child lifecycle" — all four `AggregateTests` status-derivation cases.
- "Unreadable child status fails closed" — `test_unreadable_child_status_fails_closed_to_unknown`.

## Correctness / coherence

Read `template/scripts/managed_task.py` (for `run`, `fetch_issue`, `issue_ref`, `repo`) and `template/scripts/managed_project_status.py` (for `observe`, `ProjectObservation`, `ManagedProjectStatusError`) before writing this change, and call only their existing public functions — no GitHub API or GraphQL logic is reimplemented. `parse_requirement_body` is best-effort and never raises on a hand-edited body; only the children-block parse is load-bearing for linkage/aggregation.

**Test-infrastructure finding surfaced and fixed during this work:** `tests/test_requirement_intake.py`'s conditional `sys.path` insert (`if str(TEMPLATE_SCRIPTS) not in sys.path: sys.path.insert(...)`) could be shadowed when an earlier-discovered test module (several `test_rollout_*.py`/`test_release_intent.py`/`test_managed_rollout.py` files prepend the bare `scripts/` directory and never remove it) left `template/scripts` present but no longer at the front of `sys.path`. Because every `scripts/*.py` dogfood shim runs its template target unconditionally on import (`source_adapter.run_template`, no `__name__ == "__main__"` guard), `import requirement_intake` then resolved to `scripts/requirement_intake.py` and executed its CLI with no arguments during test discovery, failing the whole module's collection. Reproduced directly with `unittest.TestLoader().discover(...)` and a `runpy.run_path` call-stack trace. Fixed by making the `sys.path` insert unconditional (always insert at position 0) in both `tests/test_requirement_intake.py` and `tests/test_orchestrate_pre_authoring.py` (the same latent pattern, not yet triggered there only because of its alphabetically earlier discovery position). Verified by reproducing the discovery call directly before and after the fix.

## Tests run

```
python3 -m compileall -q template/scripts scripts tests
python3 -m unittest tests.test_requirement_intake -v      # 17/17 passed
python3 scripts/run_test_groups.py --all                   # 13/13 groups, all passed
python3 template/scripts/openspec_lifecycle.py check        # OK (before archive)
openspec validate add-requirement-intake --strict --no-interactive   # valid
```

No material finding surfaced during this review beyond the test-infrastructure issue above, which was fixed and re-verified.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
