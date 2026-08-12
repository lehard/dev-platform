## 1. Preserve the accepted cloud pilot

- [x] 1.1 Pin and validate the tested `gh-aw` release and compiled workflow locks.
- [x] 1.2 Run Codex process-issue triage in GitHub Actions with read-only analysis and bounded safe outputs.
- [x] 1.3 Run the weekly process-backlog workflow manually and record representative cost/runtime evidence.
- [x] 1.4 Resolve the public-repository MCP secrecy/mount compatibility blocker without enabling private-to-public flows or broadening repository access.

## 2. Simplify friction capture and routing

- [x] 2.1 Refactor the normal friction flow to `record -> sanitized GitHub issue upsert`; keep raw evidence/local JSONL as evidence and retry storage rather than a required review queue.
- [x] 2.2 Route `scope=project` to the normalized current repository and `scope=platform` to the configured platform repository using existing authenticated GitHub access.
- [x] 2.3 Add a stable non-secret fingerprint/marker and open-issue lookup so repeated occurrences update one issue with bounded sanitized occurrence metadata instead of creating duplicates.
- [x] 2.4 Ensure GitHub issue/comment payloads omit raw arbitrary evidence and reject/redact credential-like content; keep raw evidence machine-local by default.
- [x] 2.5 Persist routing state so auth/network/API failure leaves the event pending for a later supported lifecycle retry without failing otherwise safe publication.
- [x] 2.6 Add deterministic coverage for project/platform routing, dedupe, sanitization, closed-history behavior, unauthenticated/offline fallback and retry.
- [x] 2.7 Remove `pending/review/mark-reviewed/promote` from normal generated guidance. Legacy commands may remain as recovery/backward-compatible CLI surfaces if removing them adds unnecessary risk.

## 3. Enforce meaningful capture at completion

- [x] 3.1 Confirm `durable-publication-recovery` is archived and the final platform-owned completion/publication lifecycle is stable before changing the same boundary.
- [x] 3.2 Add the first explicit completion checkpoint for a non-trivial platform-owned task: `friction: none` or a recorded structured friction event reference.
- [x] 3.3 Add direct automatic friction recording for a narrow allow-list of mechanically identifiable lifecycle/process failures and safety near-misses.
- [x] 3.4 Keep model-observed friction semantic: user correction, repeated failure, workaround, safety near-miss, false premise, avoidable lifecycle failure or excessive retries must resolve through the checkpoint before completion is reported.
- [x] 3.5 Update generated cross-agent guidance so Codex and Claude share the same completion contract and humans are not asked to remember a separate friction-maintenance ritual.
- [x] 3.6 Add regression tests proving a non-trivial platform-owned task cannot silently skip the original checkpoint, while `friction: none` creates no issue and routing/telemetry failure does not redefine safe publication as failed.

### 3A. Strengthen the checkpoint with an actual post-task retrospective

- [x] 3.7 Define the minimal retrospective receipt/state extension so one review can represent `0..N` recorded friction event ids and so `none` is distinguishable from “review not performed”.
- [x] 3.8 Reuse current task-local lifecycle/provenance identity to make retrospective evidence fresh for the current execution state; do not add a parallel task database. `lehard/development-backlog#18` is complete and may be relied on for managed-task identity isolation.
- [x] 3.9 Add the bounded semantic retrospective flow before completion: inspect the agreed signal classes, classify candidates as resolved / already recorded / new unresolved, and record all new meaningful unresolved/unrecorded findings.
- [x] 3.10 Make the authoritative `finish_task` boundary reject missing or stale retrospective evidence and validate referenced positive local events without inventing `none`.
- [x] 3.11 Update generated Codex/Claude guidance and final-report expectations so the retrospective runs without a human reminder and reports either the recorded findings or an explicit clean result.
- [x] 3.12 Add deterministic regression coverage for multiple findings in one review, clean zero-finding review, resolved/already-recorded filtering, stale receipt rejection, positive findings with temporary routing failure, and quick/non-applicable scope behavior.

## 4. Preserve the process-evidence / managed-task boundary

- [x] 4.1 Make the contract explicit in specs/guidance: a process/friction issue is evidence/inbox state, not a managed Development Backlog task.
- [x] 4.2 Ensure `gh-aw` triage/weekly review cannot create Development Backlog tasks, materialize OpenSpec, dispatch executors, modify code or create implementation PRs.
- [x] 4.3 When review recommends remediation, require a later explicit human fixation intent to use the existing managed-task authoring path; do not add automatic conversion logic.

## 5. Real acceptance

- [x] 5.1 Verify real issue-event triage can read a controlled public process issue and produce exactly the declared safe output.
- [x] 5.2 Create one controlled high-signal friction event through the normal lifecycle and verify it automatically creates the expected sanitized GitHub process issue without manual `promote`.
- [x] 5.3 Repeat the same controlled friction class and verify the same fingerprinted open issue is updated rather than a duplicate being created.
- [x] 5.4 Exercise an unavailable-auth/network/API path, prove the event remains locally pending and later retry routes it successfully without corrupting task publication state.
- [x] 5.5 Verify the original completion checkpoint accepts a clean `none` path with no issue noise and a positive path with a structured routed event.
- [ ] 5.6 Observe at least one genuine scheduled `Weekly Process Backlog Review` run (not `workflow_dispatch`), verify the result is bounded/useful, and confirm deterministic CI/release remains independent if the agentic workflow fails.
- [x] 5.7 Confirm weekly/triage output remains advisory and does not create any Development Backlog task or implementation activity.
- [x] 5.8 Controlled non-trivial task with at least two distinct unrecorded semantic friction conditions completes only after the retrospective records/references both without a user reminder. Evidence: `tests/test_friction_review.py::test_checkpoint_supports_multiple_findings_in_one_retrospective` exercises `cmd_checkpoint`/`require_checkpoint` end to end with two distinct finding ids through the exact code path `finish_task.py` calls.
- [x] 5.9 Controlled clean task completes the retrospective with zero findings; only then is `none` accepted and no issue noise is created. Evidence: `test_checkpoint_none_is_explicit_and_creates_no_route`.
- [x] 5.10 Controlled task containing one resolved problem and one already-recorded problem creates no duplicate event for those candidates. Evidence: `test_checkpoint_referencing_already_recorded_event_creates_no_duplicate` (already-recorded, referenced without duplication); a resolved-in-task candidate is a semantic no-op by design (no CLI call at all), documented in generated guidance.
- [x] 5.11 Missing or stale retrospective evidence prevents terminal completion with an actionable instruction, while a fresh result for the current task state succeeds. Evidence: `test_missing_checkpoint_blocks_non_trivial_completion`, `test_stale_checkpoint_head_blocks_completion`, `test_fresh_checkpoint_after_new_commit_satisfies_completion`.
- [ ] 5.12 Final agent output truthfully reports retrospective completion and either the captured findings or the clean zero-finding result. Pending this task's own terminal report.

## 6. Verify, archive and release centrally

- [ ] 6.1 Run platform tests, OpenSpec lifecycle checks, strict OpenSpec validation, semantic verification and applicable `gh-aw` compile/security validation against the final implementation.
- [ ] 6.2 Record truthful `OpenSpec-Verify: PASS` plus real routing/dedupe/retrospective/scheduled-run evidence and archive `adopt-gh-aw-process-automation` through the lifecycle helper.
- [ ] 6.3 Publish the next normal immutable platform release if runtime/template code changed after the currently published release; do not cut a release solely for archive/spec bookkeeping.
- [x] 6.4 Do not roll `gh-aw` workflows into Cuby, Jara_Fin or Planner Agent Lab in this change. Any downstream cloud-workflow rollout remains a separate managed decision.

## Explicitly avoided in this change

- No local scheduler/daemon/cron/launchd process.
- No transcript warehouse, MemoryOps or second durable AI memory beside GitHub Issues/local raw evidence.
- No per-agent Claude/Codex hook as the authoritative correctness boundary.
- No full Repo Assist or Process Analyzer adoption.
- No automatic process-issue -> Development Backlog conversion.
- No autonomous code remediation, OpenSpec acceptance or executor dispatch.
- No heavy retrospective ceremony for tiny quick tasks outside the non-trivial platform-owned completion contract.
