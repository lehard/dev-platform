## Why

In portable and light projects the developer archives by hand before finish, which is a second archive path next to the finalize job and the source of repeated archive reruns.

## What Changes

- Portable finish: required review stage (same review function), then `finalize_change`, commit, then publication; hygiene no longer expects a prior manual archive.
- `execute_requirement` portable multi-child: a verified ready child is finalized by advance before its ready receipt.
- `openspec_lifecycle.py archive` without `--finalize` refuses, naming finish or the finalize job; `--finalize` stays for the trusted archiver.
- Docs drop the developer archive command and step.
- Shipped OpenSpec configuration, explorer guidance and template contract assertions name the executable finish/advance path. Portable advance reports finalization refusals through its existing structured error boundary.

## Impact

- `template/scripts/{finish_task,execute_requirement,openspec_lifecycle,independent_review,independent_review_runner,requirement_composition}.py`, AGENTS.md, template AGENTS, docs, tests, manifest.
- Spec: completion-lifecycle (one requirement modified, two added).
