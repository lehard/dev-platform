## 1. Capability contract

- [x] 1.1 Add the `repository-goal-scan` canonical descriptor as an opt-in, explicit-only, tool-backed capability with no repository/backlog write authority.
- [x] 1.2 Add provider-neutral capability instructions covering Plan → deterministic Shard → Map → Reduce, exact-revision binding, selector limitations, candidate accounting, and human promotion.
- [x] 1.3 Document the capability in `docs/engineering/engineering-capabilities.md` as an independent architecture adaptation of Cognition's published Agentic MapReduce pattern; vendor no Cognition content/runtime.
- [x] 1.4 Add deterministic trigger/eval evidence with representative broad scans and hard negatives for ordinary local engineering tasks.

## 2. Deterministic scan adapter

- [x] 2.1 Add `repository_goal_scan.py` to source/template-managed tooling and expose it as the capability's tool adapter.
- [x] 2.2 Implement exact commit resolution and committed-tree enumeration so scan identity is not affected by uncommitted working-tree state.
- [x] 2.3 Implement the bounded v1 selector/profile schema: conservative path/inventory selection plus fixed/regex textual matching with explicit include/exclude scope and no arbitrary planner-authored shell execution.
- [x] 2.4 Emit stable selector/candidate provenance and deterministic bounded batches; reject duplicate/omitted assignment.
- [x] 2.5 Implement batch-result recording that requires every assigned candidate exactly once and rejects extras/omissions/duplicates.
- [x] 2.6 Implement read-only status and truthful finalization/coverage receipts; pending/failed work cannot yield a complete scan.

## 3. State and report boundaries

- [x] 3.1 Keep default scan manifests/results under ignored `.dev-platform/repository-goal-scan/` in source and rendered projects.
- [x] 3.2 Keep raw prompts, provider transcripts, chain-of-thought, credentials, and unrelated code copies out of scan evidence.
- [x] 3.3 Ensure reduced findings preserve candidate/batch evidence references while remaining advisory.
- [x] 3.4 Ensure no scan command creates/modifies Issues, managed tasks, PRs, Project status, application source, or production state.

## 4. Regression evidence

- [x] 4.1 Cover selector execution over a synthetic committed repository revision, including exclusions and known limitation reporting.
- [x] 4.2 Cover deterministic candidate IDs and sharding across repeated identical runs.
- [x] 4.3 Cover overlap/omission/extra candidate rejection and a valid no-findings batch.
- [x] 4.4 Cover pending and failed batches blocking complete finalization.
- [x] 4.5 Cover a fully accounted run producing a truthful `100% selected-scope` receipt while preserving selector limitations.
- [x] 4.6 Cover explicit-only triggering: broad "scan/find everywhere" requests match; implementation/debug/focused review do not.
- [x] 4.7 Run capability audit/eval, relevant focused tests, full platform validation, semantic OpenSpec verification, and write a truthful verification receipt. Archive and publication follow the repository lifecycle after this task is complete.
