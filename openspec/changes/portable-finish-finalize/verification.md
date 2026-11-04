# Verification: portable-finish-finalize

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review across the authored outcome, completeness, correctness and coherence; canonical regression tests and independent Claude review. Full selected validation passed on the unchanged authored head.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Portable finish enters the new preflight and finalization path only for an active managed change. Required independent review and the shared developer-context `finalize_change` run before archived-provenance/publication gates; finish commits the archive. Quick-task publication and archived delivery recovery preserve their existing gate order and do not import managed review machinery.
- Portable Requirement advance finalizes completed, verified active children before creating ready receipts. It re-resolves canonical provenance and refuses if no archive was produced. SystemExit refusals preserve their exact diagnostic and cause through RequirementExecutionError; no receipt is written after refusal.
- Developer archive without `--finalize` refuses before target validation or archive work, naming finish or the queue finalize job. The trusted `--finalize` entry remains available.
- Portable finalization uses the existing selected-check reuse rule. The light-project regression runs checks once, commits the archive, then reuses the same content-bound evidence in finish validation.
- Review remains required with the optional setting disabled. Queue and portable review share runtime preflight and both perspective launches; queue snapshot containment still rejects reviewer writes.
- Central/rendered OpenSpec config, explorer guidance, AGENTS and workflow/intake docs point to the executable finish/advance/queue path. Rendering contract assertions cover those instructions and manual archive refusal.
- No material conflict with the accepted specs plus the active delta was found. This semantic assessment is a documented equivalent manual review; it does not claim an unavailable opsx tool invocation or terminal publication.

## Review and regression evidence

- Initial R2 Codex execution completed with clean delegated containment. Its sandbox could not access the canonical OAuth runtime, integration checkpoint lock or machine-pool directory; none of those sandbox refusals was counted as a passing canonical check.
- Initial canonical independent review found material shipped-guidance/assertion omissions. Bounded repair used the supported prior_balanced_failure escalation to retained R3 execution after the already-completed R2 child; real delegation evidence was preserved.
- Canonical affected tests then exposed quick-task regressions from unconditional managed finalization. The active design was clarified before code repair. All four previously failing groups now pass: git_lifecycle, merge_lifecycle_resilience, protected_main_zero_handoff, publication_recovery_cli.
- 124 portable-finish/template-contract/Requirement-execution tests passed after the managed-only boundary repair.
- Fresh independent Claude review of 3afb947963d9627f60ac05fbe4c544ef6e6eacfa against the exact contribution base: spec-fidelity and engineering-quality available, zero findings; independent review ready. Earlier advisory reports are superseded by this fresh review, without claiming unrelated advisory behavior was changed.
- compileall; CI Python 3.11 compilation; Ruff; generated manifest check; managed registry validation; candidate-stage OpenSpec hygiene; strict validation of all 54 OpenSpec items; factual agent_board scope gate all passed.

## Full validation status

Canonical protected-full selected checks passed against authored head 3afb947963d9627f60ac05fbe4c544ef6e6eacfa and exact contribution base 2a1b22304a5178ce0ad3f7715dc58d3f0cc2f7d3. The evidence records all five mandatory commands as success; the complete test-group run took 1626.2 seconds. Documentation links, three-profile AGENTS rendering, Explorer validation and git diff whitespace checks also passed. Explorer reported editorial drift warnings, without validation errors.

The first obsolete run was interrupted after material review findings; the next affected precheck failed on the quick-task regression and did not start the full suite. Neither is counted as a pass. After fixing the boundary and passing all four affected groups, the canonical protected-full run executes the complete mandatory check set.

## Friction and limits

Recorded T3 events: c0537e0beae2 (sandbox limits), 36d76055c073 (validation order), b06769243369 (completed-child review repair routing), 431f886185cf (contribution selector scope waiver), 100ed0b7b686 (bounded verification missed the quick-task matrix). The factual scope gate passed independently. The task checkpoint links all five events after reviewing the complete execution path; the parent Requirement retrospective remains queue-owned after merge.

An existing compatibility import in openspec_lifecycle is unchanged; no new fallback was introduced or exercised. This task does not claim archive, merge or terminal Requirement closure at the developer handoff.
