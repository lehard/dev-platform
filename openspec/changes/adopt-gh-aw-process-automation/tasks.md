## 1. Pin and validate the gh-aw foundation

- [x] 1.1 Select one exact tested GitHub Agentic Workflows (`gh-aw`) release, record the pin in platform maintenance documentation/configuration, and verify installation with `gh aw doctor` for `lehard/dev-platform`.
- [x] 1.2 Add deterministic validation for agentic workflow sources/compiled lock files so source/lock drift or unsupported frontmatter fails review before merge.
- [x] 1.3 Document the single required secret contract (`OPENAI_API_KEY`) without storing or echoing the secret value.

## 2. Add the central dev-platform cloud pilot

- [x] 2.1 Import/adapt the maintained `githubnext/agentics` issue-triage pattern into a narrowly scoped `dev-platform` process-issue triage workflow using `engine: codex`.
- [x] 2.2 Restrict the triage trigger to controlled process/platform-candidate issues and restrict writes to allow-listed `safe-outputs` (labels/comments only in v1).
- [x] 2.3 Add a weekly fuzzy-schedule + `workflow_dispatch` process-backlog review workflow that produces one bounded human-readable summary and does not modify code, create implementation PRs, merge, approve or close source issues.
- [x] 2.4 Add conservative `timeout-minutes` and `max-ai-credits` to each agentic workflow and document how to inspect actual usage with `gh aw audit`/`gh aw logs` before increasing limits.
- [x] 2.5 Compile with the pinned `gh-aw` version, commit generated lock workflows, and run applicable workflow/security validation.

## 3. Simplify friction routing to GitHub Issues

- [ ] 3.1 Extend the existing friction helper so a sanitized high-signal event can route automatically to `scope=project` (current repository) or `scope=platform` (configured platform repository) without routine manual `promote`.
- [ ] 3.2 Add a stable non-secret fingerprint/marker and open-issue lookup so repeated occurrences update one issue rather than create duplicates.
- [ ] 3.3 Keep raw evidence machine-local by default; ensure routed issue bodies/comments contain only sanitized structured fields and never credentials or raw arbitrary evidence.
- [ ] 3.4 Make failed GitHub routing durable: retain pending local events and retry them during a later supported lifecycle invocation without blocking otherwise safe task publication.
- [ ] 3.5 Add unit/integration coverage for project routing, platform routing, dedupe, sanitization, unauthenticated/offline fallback, and retry.

## 4. Enforce capture at completion without racing publication work

- [ ] 4.1 Wait until the active `durable-publication-recovery` change has stabilized its `finish_task`/publication integration surface before editing the same lifecycle path.
- [ ] 4.2 Add direct automatic friction recording for deterministic lifecycle failures and other machine-detectable high-signal process failures.
- [ ] 4.3 Add one mandatory non-trivial completion checkpoint for model-observed friction (user correction, repeated failure, safety near-miss, workaround, false premise, avoidable CI/lifecycle failure, excessive retries) and require a structured event when the answer is positive.
- [ ] 4.4 Update generated agent guidance so humans are not instructed to remember `promote`, weekly local review, cron, launchd or a separate friction-maintenance ritual.
- [ ] 4.5 Add regression tests proving a task cannot silently skip the checkpoint while telemetry/routing failure itself does not redefine a safely published task as failed.

## 5. Pilot acceptance

- [ ] 5.1 With `OPENAI_API_KEY` configured as a repository Actions secret, run the triage workflow manually or with a controlled test issue and verify Codex executes in GitHub Actions without local-computer participation.
- [ ] 5.2 Verify agent analysis is read-only and every GitHub write is performed only through declared safe outputs; confirm no implementation PR/code write path exists in v1.
- [ ] 5.3 Verify one repeated friction case updates the existing fingerprinted issue instead of opening a duplicate.
- [ ] 5.4 Run the backlog review manually, then observe at least one scheduled review; verify the output is concise/actionable and deterministic CI/release remains independent if the agentic workflow fails.
- [ ] 5.5 Inspect representative run cost/runtime with `gh aw audit`/`gh aw logs`; record acceptance evidence and adjust caps only if justified by observed usage.

## 6. Validate and release centrally

- [ ] 6.1 Run platform tests, OpenSpec lifecycle checks, strict semantic OpenSpec verification, and applicable `gh-aw` compile/validation/security checks.
- [ ] 6.2 Record truthful `OpenSpec-Verify: PASS` plus the actual cloud-pilot evidence, archive `adopt-gh-aw-process-automation`, and publish through protected main.
- [ ] 6.3 Publish the next normal immutable platform release containing the central integration.
- [ ] 6.4 Do not roll `gh-aw` workflows into Cuby, Jara_Fin or Planner Agent Lab in this change. Open a follow-up OpenSpec only after the central pilot is proven stable and useful.

## Logical commit boundaries

1. gh-aw pin/validation + cloud workflow sources/locks.
2. friction routing/deduplication + tests.
3. completion checkpoint/guidance after publication-lifecycle dependency stabilizes.
4. pilot evidence + OpenSpec verification/archive.
