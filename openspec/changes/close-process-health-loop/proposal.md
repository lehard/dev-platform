# Proposal: Close the process-health loop

## Why

Dev Platform already captures and deduplicates friction, routes sanitized process issues, performs bounded triage, and produces a weekly advisory review. The remaining gap is lifecycle coherence: evidence that has been accepted into managed work stays indistinguishable from unmanaged evidence, terminal fixes do not resolve their source process issues, and later reviews can reason from stale issue text without an explicit current-repository boundary.

This change closes that loop using the existing GitHub issues, managed-task lifecycle and agentic-maintenance workflows rather than adding a second problem-management system.

## What Changes

- Add explicit, bounded linkage from managed tasks to the process issues that motivated them.
- Mark linked evidence as managed while it remains open and close only that linked evidence after terminal managed success.
- Make weekly review freshness-aware with an exact `main` SHA, previous-review boundary, recent managed/merged work and root-cause clustering.
- Promote the proven central contract into the managed-project template/rollout path after central acceptance.

## Impact

- Modified specifications: `platform-lifecycle`, `agentic-maintenance`, `project-factory`.
- Expected surfaces: managed-task authoring/completion, friction/process issue metadata and labels, weekly agentic workflow source/lock, template workflow/label provisioning, canonical ChatGPT Project protocol, focused lifecycle/workflow tests and docs.
