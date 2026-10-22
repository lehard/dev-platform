## Why

After the developer handoff accepts a head behind a mergeable `main` (handoff-mergeable-task-base), the queue still has to integrate it. The platform manifest is a sorted JSON file with one line per template file, so two PRs that change neighbouring template files produce a textual conflict in it. Today the queue re-derives only archive-derived specs; any other conflict, including a manifest conflict, becomes an agent integration-repair job. Regenerating the manifest is deterministic and needs no agent.

## What Changes

- When preparing a candidate on current `main`, the queue reads `[[generated_files]]` from its own default-branch checkout. If the merge conflicts only in declared generated files and archive-derived spec paths, or a declared generated file changed on both sides since the admission base, the queue merges in a disposable checkout, re-derives archived specs as today, runs each declared `regenerate` command from the trusted default-branch checkout with `{tree}` set to the merged checkout, commits the merge and pushes it lease-protected as a recorded coordinator update.
- Required checks run on that head and gate the merge as before. A failed regeneration, a remaining conflict, or a conflict in any other file becomes the existing bounded integration repair.
- Recovery of an unrecorded coordinator update also accepts a merge that differs from both parents only in archive-derived specs and declared generated files.
- The App token never executes pull-request-controlled code: the generator and its declaration come from the default branch; the merged tree is input data.

- Owner decision 2026-10-22 (see design): declared generated files leave task-content identity, so regeneration does not reset content-bound gates of an archived candidate. Each declaration names the required `check` that verifies the file, and that check must be in `[settings].full_commands`; otherwise the declaration fails explicitly. Identity reads the declaration at the main merge base, never from the candidate. Every other task path stays in identity.

## Impact

- `template/scripts/publication_queue.py` (`_prepare`), `template/scripts/post_review_finalization.py` (generalized re-derivation, `derived_merge_only`), `template/scripts/task_content_identity.py` (`review_exclusion`), `template/scripts/_platform_common.py` (declaration `check`), `dev-platform/checks.toml`.
- Specs: publication-queue, completion-lifecycle. Docs: `docs/engineering/chat-coordinator.md` if it describes integration bookkeeping.
