# Tasks

## 1. Registry and rollout tooling

- [ ] 1.1 Add a dependency-light managed-project registry with explicit `managed`/`candidate` states.
- [ ] 1.2 Add registry validation and rollout-matrix generation.
- [ ] 1.3 Add a per-project exact-version Copier rollout helper with fail-closed preflight/conflict checks.

## 2. GitHub Actions orchestration

- [ ] 2.1 Add a manual/release-dispatched managed rollout workflow using a SHA-pinned GitHub App token action.
- [ ] 2.2 Wire successful immutable release publication to dispatch the exact released version.
- [ ] 2.3 Ensure rollout opens reviewable PRs and never auto-merges by default.

## 3. Documentation and adoption boundary

- [ ] 3.1 Document one-time GitHub App setup, permissions, registry ownership and rollout recovery.
- [ ] 3.2 Fix obsolete adoption guidance about private cross-repository reusable CI access.
- [ ] 3.3 Update README/release policy so managed rollout and first-time adoption are clearly separated.

## 4. Tests and validation

- [ ] 4.1 Add unit tests for registry, answers metadata/version validation, branch naming and conflict detection.
- [ ] 4.2 Add workflow/template contract tests for exact-version rollout, action SHA pinning and no auto-merge.
- [ ] 4.3 Run compile/unit tests, registry validation, strict OpenSpec validation and existing Copier upgrade smoke.

## 5. Completion

- [ ] 5.1 Perform semantic OpenSpec verification across completeness, correctness and coherence and record truthful PASS evidence only after findings are resolved.
- [ ] 5.2 Archive the change and confirm accepted rollout behavior is represented under `openspec/specs/` before publication.
