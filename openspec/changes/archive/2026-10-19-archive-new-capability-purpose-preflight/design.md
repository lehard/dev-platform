## Context

- `archive_change` order today: target check → privacy → managed identity → `require_static_archive_readiness` (tasks, receipt, independent-review receipt, routing, automated marker) → committed diff (platform) → review / selected checks → `require_ready` → `openspec validate <change> --strict` → `openspec archive --yes` → `openspec validate --all --strict`.
- OpenSpec 1.13.2: a delta `## Purpose` is used only when archive creates the capability; otherwise archive writes the `TBD - created by archiving change … Update Purpose after archive.` sentence, and `validate --all --strict` flags it as a placeholder.
- Composition finalization archives each child in manifest order inside a disposable harness checkout with `--finalize`; `trusted_archiver` raises `archive failed: <last 400 chars>`.

## Decisions

1. **Purpose is authored in the delta.** For every `openspec/changes/<name>/specs/<cap>/spec.md` where `openspec/specs/<cap>/spec.md` does not exist (and no earlier change in the same ordered set creates it), the delta must contain a `## Purpose` section whose text is non-empty and is not a placeholder (`TBD`, `TODO`, `FIXME` prefixes, or the archive placeholder sentence). The predicate is pure file reading so it runs without the OpenSpec CLI and without Git. Length and wording quality remain OpenSpec's strict-validation concern (caught by rehearsal).
2. **One shared predicate.** `archive_content_problems(root, changes)` returns a list of human-readable problems for an ordered list of active changes: missing/incomplete tasks and new-capability Purpose. `require_static_archive_readiness` raises on it; `handoff_gates`, composition offer/review and composition finalization call it with their child order. No second copy of the rules.
3. **Committed package before spend.** For a non-finalize archive, `git status --porcelain --untracked-files=all` over `openspec/changes/<name>` and `openspec/specs` must be empty except lifecycle-generated evidence (the existing review-evidence set, `automated-checks.json`, `evidence/`). The diagnostic lists the paths and `git add … && git commit`. `--finalize` keeps its trusted-coordinator contract and is exempt, like the committed-diff gate.
4. **Rehearse, then mutate.** After all cheap and review/check gates and `validate <change> --strict`, archive copies `openspec/` into a temporary directory, runs `openspec archive <name> --yes` and `openspec validate --all --strict --no-interactive` there with captured output, and stops on failure with the summarised items. The checkout is untouched. Cost is seconds.
5. **Restore on unexpected post-validation failure.** The real archive captures a copy of `openspec/` immediately before `openspec archive`. If the real post-validation fails (non-determinism, concurrent edit), the lifecycle replaces `openspec/` with the captured copy, then exits non-zero with the failing items and states that the tree was restored and the same command can be rerun. Restoration is not a fallback: the command still fails; it only removes the half-archived state the command itself created. A restoration error is raised with both errors.
6. **Readable failures.** `openspec_failure_summary(output)` keeps lines with `✗`, `[ERROR]`, `[WARNING]`, `Error`/`error:` and lifecycle diagnostics, dropping progress/INFO lines; when no such line exists it returns the whole output (never a tail). Used by rehearsal/recovery and by `post_review_finalization.trusted_archiver` and `_openspec`.
7. **Early composition readiness.** `publish_composition` evaluates the predicate on its harness checkout before offering a review and raises a `ContributionError` naming the children and problems; `execute_composition_review` re-checks before launching reviewers; `execute_composition_finalize` checks all children before archiving the first.

## Rejected alternatives

- Writing a generated Purpose at archive: invents product text; the Requirement prefers the authored source and OpenSpec already supports it.
- Editing the main spec after archive automatically: same, and hides the authoring defect.
- Relying on `git checkout`/`git restore` for recovery: would discard unrelated user changes under `openspec/`; the captured copy restores exactly what the command changed.
- Keeping a longer output tail: still arbitrary truncation.

## Risks and mitigations

- *Rehearsal and real archive diverge.* Both run the same CLI on the same tree; recovery covers the residual case.
- *Exempt evidence set too broad.* Reuse the existing review-evidence predicate plus the two automated evidence names; authored files are never exempt.
- *Downstream projects with legacy active changes lacking Purpose.* They fail at archive with an exact instruction instead of after mutation; no previously passing valid archive is rejected because a placeholder Purpose already failed `validate --all --strict`.
