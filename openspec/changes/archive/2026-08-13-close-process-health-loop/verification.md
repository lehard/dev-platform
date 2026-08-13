# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active proposal/design/delta specs against the implemented lifecycle, workflow, template and focused tests; structural OpenSpec validation; risk-selected automated checks.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The package manifest and task-local canonical provenance preserve a bounded `process_evidence` list; authoring validates each reference as an open, accessible `process` issue and idempotently adds `process:managed` plus one backlink.
- Resolution is reachable only from the existing terminal delivery paths after merged/local-main/Project `Done` reconciliation. It closes only explicitly linked, still-open `process` issues as `completed`, retains non-terminal evidence, and reuses its deterministic marker on retry.
- The weekly review source records its current-state boundary, reads only bounded GitHub context, performs no source-evidence mutation, and instructs root-cause clustering and stale-evidence checking.
- The managed-project template supplies the same workflow, label provisioning and bounded configuration while preserving project-local versus central platform routing.
- The acceptance review in `process-health-review.md` is based on the exact current `main` SHA and makes no unsupported historical backfill or remote mutation.

## Executed checks

- `python3 scripts/validate_agentic_workflows.py`
- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/close-process-health-loop/automated-checks.json`
- `openspec validate close-process-health-loop --strict --no-interactive`
