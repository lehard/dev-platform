# Design: Deterministic coverage around agent reasoning

## Context

Whole-repository investigations have a different reliability problem from local coding tasks. A search-driven agent can spend most of its context discovering where to look and has no finite queue whose exhaustion proves that the selected work was actually processed.

Cognition's Agentic MapReduce separates reasoning from bookkeeping: reasoning authors selectors and investigates shards, while deterministic machinery turns selectors into a finite work queue and accounts for every shard. The reusable idea is the deterministic coverage boundary, not the Devin product or its orchestration runtime.

Dev Platform already has the right promotion boundary: review/evidence does not become implementation until a human accepts work and the ordinary task lifecycle is entered.

## Decisions

1. **Create a separate optional capability.** Do not broaden `architecture-health-review`; that capability deliberately prefers bounded named scopes and remains advisory architecture review.
2. **Make invocation explicit-only in v1.** Whole-repository scans can be expensive and should not appear because a model casually infers that a local request "might benefit" from one.
3. **Use a tool-backed capability for coverage truth.** `scripts/repository_goal_scan.py` (and its template/rendered counterpart) owns deterministic revision resolution, selector execution, candidate IDs, sharding, batch-result validation, status, and final coverage receipts.
4. **Scan the committed Git tree, not ambient working-tree bytes.** Resolve the requested/default revision to a full commit SHA and enumerate/read tracked content from that revision. Dirty local changes therefore cannot silently contaminate the scan identity.
5. **Use a bounded selector schema in v1.** Support explicit/path-glob inventory selection plus bounded textual fixed/regex matching implemented without arbitrary shell evaluation. Selectors have stable IDs, declared path scope/exclusions, and evidence provenance. A planner needing AST/type/call-graph semantics must widen to a conservative supported selector or disclose the limitation.
6. **Signals are the deterministic work units.** Each selector match yields a stable candidate/signal ID derived from revision + selector + location/provenance. Signals are assigned exactly once to bounded batches; sharding rejects omissions/overlaps.
7. **Workers must account for candidates, not merely batches.** A valid batch result names every assigned candidate exactly once with `finding` or `no-finding`; runtime failure remains an explicit failed batch and blocks a complete receipt.
8. **Do not build a second agent scheduler.** Capability instructions define Plan/Map/Reduce. Native safe subagent/delegation can accelerate Map, otherwise the active executor processes batches sequentially. The platform adapter does not own provider sessions.
9. **Reducer reasons over structured conclusions.** Final reasoning should normally consume per-batch structured findings/no-findings and evidence references rather than re-searching the entire repository. It may inspect cited surrounding code when needed to reconcile/deduplicate.
10. **Coverage has two layers.** The adapter can prove queue accounting; it cannot prove selector recall. Final output therefore reports selected-scope processing separately from selector confidence/limitations.
11. **No automatic remediation.** Findings are advisory evidence. Human-selected work enters the existing intake lifecycle; no direct Issue/PR/task creation is added.
12. **Keep run state local.** Default run state lives under `.dev-platform/repository-goal-scan/` and is ignored. Persisting a reusable selector profile or report into repository source is a separate explicit reviewed change.

## Proposed adapter surface

A small CLI should provide a deterministic lifecycle similar to:

- `plan --profile <scan-profile.json> [--revision <ref>] --out <run-dir>`
  - resolve exact commit;
  - validate selector schema;
  - enumerate the committed tree;
  - execute supported selectors;
  - emit candidates and deterministic batches.
- `record --manifest <manifest.json> --batch <id> --result <batch-result.json>`
  - validate exact batch identity;
  - require every assigned candidate exactly once;
  - reject extras/omissions/duplicates;
  - record a valid result or explicit failure.
- `status --manifest <manifest.json>`
  - read-only summary of batches/candidates: pending, valid, failed.
- `finalize --manifest <manifest.json> --out <coverage.json>`
  - produce `complete` only when all selected candidates/batches have valid accounting;
  - otherwise produce/return an incomplete state and never a complete-coverage claim.

The exact filename/schema may be refined during implementation only where it preserves these semantics; material intent changes require updating the OpenSpec artifacts first.

## Scan profile

The profile should contain at least:

- goal and bounded acceptance/question;
- selector IDs/types/patterns;
- include/exclude path scope;
- explicit limitations/known blind spots;
- shard bound (candidate count and/or approximate bytes);
- optional human notes for the reducer.

No raw prompt, chain-of-thought, credential, or provider transcript is part of durable evidence.

## Findings

A map finding should carry:

- stable finding ID;
- source candidate ID(s) and batch ID;
- location/evidence reference;
- bounded description;
- confidence;
- impact/priority rationale;
- uncertainty/counter-evidence where material.

The final reducer can merge findings but must preserve source IDs so evidence is inspectable.

## Verification

- unit tests for revision binding, selector matching, stable candidate IDs, deterministic sharding, overlap/omission rejection, exact candidate accounting, failed/pending finalization, and complete receipts;
- contract tests that source/template adapters stay aligned and local state is ignored;
- capability descriptor/hash/audit tests and deterministic trigger fixture with positive broad-scan prompts and hard negatives for local implementation/debug/review;
- semantic OpenSpec verification and ordinary platform full validation before delivery.
