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
- [x] 3.2 Add the smallest explicit completion checkpoint for a non-trivial platform-owned task: `friction: none` or a recorded structured friction event reference. Reuse the existing lifecycle; do not build a parallel state machine.
- [x] 3.3 Add direct automatic friction recording for a narrow allow-list of mechanically identifiable lifecycle/process failures and safety near-misses.
- [x] 3.4 Keep model-observed friction semantic: user correction, repeated failure, workaround, safety near-miss, false premise, avoidable lifecycle failure or excessive retries must resolve through the checkpoint before completion is reported.
- [x] 3.5 Update generated cross-agent guidance so Codex and Claude share the same completion contract and humans are not asked to remember a separate friction-maintenance ritual.
- [x] 3.6 Add regression tests proving a non-trivial platform-owned task cannot silently skip the checkpoint, while `friction: none` creates no issue and routing/telemetry failure does not redefine safe publication as failed.

## 4. Preserve the process-evidence / managed-task boundary

- [x] 4.1 Make the contract explicit in specs/guidance: a process/friction issue is evidence/inbox state, not a managed Development Backlog task.
- [x] 4.2 Ensure `gh-aw` triage/weekly review cannot create Development Backlog tasks, materialize OpenSpec, dispatch executors, modify code or create implementation PRs.
- [x] 4.3 When review recommends remediation, require a later explicit human fixation intent to use the existing managed-task authoring path; do not add automatic conversion logic.

## 5. Real acceptance

- [x] 5.1 Verify real issue-event triage can read a controlled public process issue and produce exactly the declared safe output.
- [x] 5.2 Create one controlled high-signal friction event through the normal lifecycle and verify it automatically creates the expected sanitized GitHub process issue without manual `promote`.
- [x] 5.3 Repeat the same controlled friction class and verify the same fingerprinted open issue is updated rather than a duplicate being created.
- [x] 5.4 Exercise an unavailable-auth/network/API path, prove the event remains locally pending and later retry routes it successfully without corrupting task publication state.
- [x] 5.5 Verify the completion checkpoint accepts a clean `none` path with no issue noise and a positive path with a structured routed event.
- [ ] 5.6 Observe at least one genuine scheduled `Weekly Process Backlog Review` run (not `workflow_dispatch`), verify the result is bounded/useful, and confirm deterministic CI/release remains independent if the agentic workflow fails.
- [x] 5.7 Confirm weekly/triage output remains advisory and does not create any Development Backlog task or implementation activity.

## 6. Verify, archive and release centrally

- [ ] 6.1 Run platform tests, OpenSpec lifecycle checks, strict OpenSpec validation, semantic verification and applicable `gh-aw` compile/security validation against the final implementation.
- [ ] 6.2 Record truthful `OpenSpec-Verify: PASS` plus real routing/dedupe/checkpoint/scheduled-run evidence and archive `adopt-gh-aw-process-automation` through the lifecycle helper.
- [ ] 6.3 Publish the next normal immutable platform release if runtime/template code changed after the currently published release; do not cut a release solely for archive/spec bookkeeping.
- [x] 6.4 Do not roll `gh-aw` workflows into Cuby, Jara_Fin or Planner Agent Lab in this change. Any downstream cloud-workflow rollout remains a separate managed decision.

## Explicitly avoided in this change

- No local scheduler/daemon/cron/launchd process.
- No MemoryOps or second durable AI memory beside GitHub Issues/local raw evidence.
- No per-agent Claude/Codex hook as the correctness boundary.
- No full Repo Assist or Process Analyzer adoption.
- No automatic process-issue -> Development Backlog conversion.
- No autonomous code remediation, OpenSpec acceptance or executor dispatch.
