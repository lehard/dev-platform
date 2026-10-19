## Why

`openspec archive` writes `TBD - created by archiving change <name>. Update Purpose after archive.` as the Purpose of every new capability whose delta carries no `## Purpose`. The platform's pre-archive `validate <change> --strict` accepts such a delta, the change is then moved and the main spec materialised, and only the final `validate --all --strict` fails, leaving a half-archived tree that was repaired by hand eight times in a downstream project and again in Dev Platform composition finalization (lehard/dev-platform#533, #537). Related late failures in the same archive input contract: archive accepted uncommitted task/receipt state (downstream #33), composition finalization discovered unticked child tasks only after three review rounds (#536), and the finalization error kept only the last 400 characters of output, hiding the failing item (#537).

OpenSpec 1.13.2 already reads `## Purpose` from a delta when it creates the capability (reproduced: the main spec gets the authored Purpose and `validate --all --strict` passes). The defect is purely platform orchestration.

## What Changes

- Archive preflight (`openspec_lifecycle.py archive`) rejects, before review, checks, evidence writes or mutation:
  - a delta for a capability absent from `openspec/specs` whose `## Purpose` is missing, empty or a placeholder (`TBD`/`TODO`/`FIXME` or the archive placeholder sentence), naming the delta file and the section to add;
  - uncommitted or untracked authored package files (proposal, design, tasks, delta specs, `verification.md`) or main-spec files, naming the paths and the commit command; lifecycle-generated evidence written by the helpers themselves stays exempt.
- Archive rehearsal: before mutating the checkout, archive runs `openspec archive` and `openspec validate --all --strict` in a disposable copy of `openspec/`; a failure stops archive with the failing items and the checkout untouched.
- Resumable recovery: if the real post-archive strict validation still fails, the lifecycle restores the exact pre-archive `openspec/` tree it captured, reports the failing items, and the same archive command can be rerun after the fix; no manual spec edit is required.
- Failure reporting: archive and finalization report the failing validation items (`✗` items, `[ERROR]`/`[WARNING]` lines, lifecycle diagnostics) instead of a fixed-length output tail.
- Readiness before spend: a shared `archive_content_problems` predicate (tasks complete and meaningful new-capability Purpose, evaluated in contribution order) runs at developer handoff (`pr_review_gate.handoff_gates`), before a composition review is offered or launched, and before composition finalization archives any child.
- `docs/engineering/openspec-workflow.md` documents delta `## Purpose` authoring and the recovery behaviour.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `completion-lifecycle`: archive input preflight, rehearsal, recovery, readable failures and early archive-readiness for candidates and compositions.

## Impact

`template/scripts/openspec_lifecycle.py`, `template/scripts/post_review_finalization.py`, `template/scripts/pr_review_gate.py`, `template/scripts/requirement_composition.py`, `docs/engineering/openspec-workflow.md`, tests and the regenerated platform manifest. Ships to downstream through the normal release; downstream archive gains the same preflight.

The archive ↔ lifecycle-hygiene cycle (downstream #5) is already closed by the exact-target hygiene exemption (Requirements #386/#417, `Archive hygiene exempts only its exact target`); this change keeps it and adds a regression assertion only.

## Non-goals

Changing the OpenSpec CLI or its validation rules; weakening strict validation or any existing archive gate; inventing Purpose text automatically; model routing, workspace permissions or handoff clusters.
