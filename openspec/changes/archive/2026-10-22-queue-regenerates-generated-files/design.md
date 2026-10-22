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

## Owner decision 2026-10-22: generated files leave task-content identity

During implementation the supervisor found that the derived merge alone cannot deliver the Requirement for a real candidate. A queue candidate is archived, and the generated manifest is one of its task paths. Regenerating it on the new main changes task-content identity (`equivalent_proofs` accepts a base move only when no task path changed). The derived merge then refuses with "changed the task-content identity", and gates bound to that identity (finalization, required checks) send the candidate back through finalize or review. lehard/dev-platform#628 hit the same effect. The owner chose, verbatim: «Вариант A: включи в I2 исключение объявленных сгенерированных файлов из task-content identity (объявление читать из main, только файлы, которые проверяет обязательный CI-чек), с тестами на архивированном кандидате.» The coordinator relayed the bounds:

1. The exclusion applies to both review identity and composition identity.
2. Every other task path stays in identity.
3. A declared file without a required CI check fails explicitly instead of being excluded silently.
4. Tests on an archived candidate cover three cases: manifest-only regeneration keeps identity and gates; a manifest change together with an ordinary task path change changes identity; the declaration comes from main.

Decisions:

- **Declaration shape.** Each `[[generated_files]]` entry now has exactly `path`, `regenerate` and `check`, where `check` is the argv of the required check that verifies the file. The entry is valid only if `check` is listed (as the same command string) in `[settings].full_commands`, the repository-owned protected full validation set of that same check configuration. Otherwise the reader raises and names the file. Dev Platform declares `check = ["python3", "scripts/generate_platform_manifest.py", "--check"]` and adds that command to `full_commands`.
- **Where identity reads the declaration.** `review_exclusion`, which review identity, composition identity and the review path partition all share, reads the declaration at `merge-base(HEAD, origin/<main>)`. That is always a main commit, never candidate content. It excludes exactly the declared paths. A missing check configuration or a malformed declaration at that commit raises.
- **Queue.** Because the regenerated file is no longer in identity, the derived merge's identity check and the content-bound gates hold for an archived candidate whose only main-side task-path change is a declared generated file. An ordinary task path changed by the merge still changes identity.
- **Rollout cost.** Once this lands, candidates in flight that changed the manifest compute a new identity (the manifest leaves their digest) and need fresh gates once. The coordinator times the merge.
