## Context

`review_is_required` is the one predicate used by `finish`, archive, publication and status, and every review function takes the change directory that holds the request, reports and dispositions. A quick task has neither provenance nor a change directory.

## Decisions

**Risk rule.** `risky_paths(root)` lists the paths of the diff from the merge base with `origin/<main_branch>`, drops the files declared in `[[generated_files]]`, and matches the rest against the `[[protected]]` globs with the glob semantics of `platform_divergence.py`. Exactly one of `dev-platform/protected-surface.toml` and `template/dev-platform/protected-surface.toml` must exist. In the template layout a path is rendered first: `template/` and `.jinja` are removed, and a path outside `template/` is matched as it is. Both surfaces, neither of them, or an unreadable or empty list stop with an error naming it.

**Required predicate.** `review_is_required(root, change)` becomes enabled and risky. `change` no longer decides it, so quick and managed share it. A quick task calls the same predicate.

**Quick target.** `quick_review_path(root)` is `<git dir>/dev-platform/independent-review/`. The existing functions keep their `change` parameter and receive this directory; the few places that read a change name or a repository-relative path branch on `is_quick(change)`: name, task content (`quick_content_identity`), the path partition, reviewer inputs and the request paths. The commands take the reserved target `quick-task`, so every existing next-step message works unchanged. There are no contract files for a quick task, so `spec-fidelity` reads the accepted rules only through the guidance list and its objective says so.

**Finish.** After `validate_or_reuse`, and after the GitLab `run_checks`, `finish` calls `ensure_review_evidence` for a risky quick task. It prints whether a review ran and why. `--no-checks` does not skip it. A managed change keeps the review in `finalize_portable_change`.

**Outcome.** `ensure_review_evidence` and `_blocking_message` already stop on a finding or an unavailable perspective, and name the next command. They are reused; for a quick task the commands name `quick-task`.

**Provider.** A quick task has no durable route, so this repository sets `provider = "claude"`. Without a provider the existing limitation stops the review.

## Risks

A risky `finish` costs two reviewer launches plus one readiness probe. Quick review evidence is local to the worktree: it gates `finish` and is not visible in the PR.
