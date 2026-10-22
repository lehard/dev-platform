## Context

The developer gate (`classify_task_base_currency`) is stricter than the queue integration rule (publication-queue: "Path overlap alone SHALL NOT block"). The queue performs the real integration and runs required checks on the merged head; the developer's evidence binds the task head.

## Decisions

- **Classification.** For a head behind `main`: missing merge base raises as today. Run `git merge-tree --write-tree --name-only --no-messages head main`. Clean merge: `behind-mergeable`, with `overlapping` = paths changed on both sides since the merge base. Conflicts: subtract declared generated paths; if none remain, `behind-mergeable` with `generated_conflicts`; otherwise `reconcile-required` naming the remaining conflicts. The state `behind-disjoint` is retired from new output; a disjoint head is simply `behind-mergeable` with no overlap.
- **Declaration location.** `[[generated_files]]` in the committed check configuration (`paths.checks`, `dev-platform/checks.toml` here). Each entry has `path` (a repository-relative file) and `regenerate` (argv list containing the `{tree}` placeholder, run from a trusted checkout of the default branch). The reader takes a commit and reads the file with `git show <commit>:<path>`; the path comes from the required `paths.checks` key, and a missing key or file at that commit is an explicit error. No `[[generated_files]]` table means none declared. Duplicate or malformed entries are errors.
- **Trust.** The gate reads the declaration from the observed `main` commit, never from the candidate head or working tree.
- **Generator.** `generate_platform_manifest.py --root <dir>` hashes `<dir>/template` with the generator's own code. Without `--root`, behavior is unchanged.
- **Evidence.** `TaskBaseCurrency.evidence()` returns `{"contract": "behind-mergeable", "main", "base", "overlapping", "generated_conflicts"}`. No reader validates the old contract name, so earlier evidence stays valid.

## Risks

- The developer's checks ran on the unintegrated head; a semantic interaction with `main` is caught by required checks on the integrated head and handled by integration repair, as the BR accepts.
