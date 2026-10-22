## Context

`_prepare` handles three cases: head already contains main; overlap confined to archive-derived specs (re-derive and push a coordinator update); otherwise GitHub `update-branch`, where a conflict becomes integration repair. `rederive_archived_specs` already merges in a disposable checkout, resolves its own paths, verifies the merge parents and that both-sides differences stay within its paths, and pushes lease-protected.

## Decisions

- **One derived-merge path.** Generalize re-derivation into a derived merge that resolves archive-derived spec paths (when the candidate archived deltas) and declared generated files in one merge commit. A candidate with no archived deltas but a generated-file conflict uses the same path.
- **Trigger.** The derived merge runs when `merge_conflicts(head, main)` is non-empty and all of them are derived paths, or when a declared generated path is in `changed(base..main) ∩ task_paths`. Otherwise `update-branch` and integration repair stay unchanged.
- **Regeneration.** Each declared `regenerate` argv runs with cwd = the queue's trusted default-branch root and `{tree}` replaced by the disposable checkout path; the resulting file is staged. A non-zero exit, a missing output or any remaining unmerged path raises `RederivationFailed`, which becomes integration repair.
- **Bounded result.** As today, the commit must have parents `[head, main]`, and paths that differ from both parents must be within derived paths. `derived_merge_only` accepts the same union for unrecorded-update recovery.
- **Declaration source.** The queue reads the declaration through the reader from handoff-mergeable-task-base at its own default-branch `HEAD`.

## Risks

- If the candidate changes the generator, the default-branch generator may produce a different manifest; the required `--check` on the integrated head fails and integration repair handles it.
