# Design: Lifecycle-wide file-scope coordination

## Keep file-level coordination simple

The current file-path claim is the authoritative hard-overlap unit. This change does not add line/hunk locks. When two tasks truly can edit distinct regions of the same file safely, the exception is explicit human/operator acknowledgment rather than a more complex sub-file locking system.

## Acknowledgment evidence

An acknowledgment records the current task identity, conflicting active task identity, exact repository-relative paths and a bounded reason. It authorizes only that observed overlap. New overlapping paths or materially changed task identity are not covered.

The evidence should live with existing machine-local coordination state and remain bounded; it is not a durable product decision log.

## Admission

Unacknowledged hard file overlap remains `WAIT`. A valid acknowledgment permits `RUN` while preserving the truthful declared scope. Soft overlap remains a warning.

## Scope evolution

Before expensive full/protected validation and immediately before publication, the platform recomputes factual changed-file scope against active claims. A new unacknowledged hard overlap blocks further costly/delivery work while the conflicting task is active. If the sibling task has completed, its stale claim does not block.

## Managed status

A genuine coordination wait may project to `Blocked`; retry/resume re-evaluates current active claims and returns to `In progress` when safe. No background scheduler or autoresume is introduced.
