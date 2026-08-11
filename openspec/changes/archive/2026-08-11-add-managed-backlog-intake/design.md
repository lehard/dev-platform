## Context

The platform already owns two strong boundaries:

1. OpenSpec owns non-trivial planning inside a repository.
2. dev-platform owns safe execution from synchronization/start through checks, verification/archive and publication.

What is missing is an intake adapter from the cross-project Development Backlog into repository-local OpenSpec. The user wants ChatGPT to finish product planning while conversation context is fresh, but does not want every quick coding request to become backlog ceremony.

The current target state also includes two active changes with nearby but distinct responsibilities. `adopt-gh-aw-process-automation` adds bounded friction/process maintenance in GitHub; `durable-publication-recovery` changes publication recovery. Managed-task intake must remain orthogonal to both.

## Goals

- Preserve the product decision made in ChatGPT without requiring a second model to reconstruct it.
- Keep Development Backlog useful as a queue of planned managed work rather than a log of every agent action.
- Make the handoff into OpenSpec deterministic, inspectable and safe.
- Keep all existing branch/worktree/check/publication behavior unchanged after intake.
- Work for all workflow profiles and both new and reviewed existing-project updates.

## Non-goals

- Watching `Ready` and automatically scheduling workers.
- Project status mutation.
- Replacing OpenSpec CLI/schema logic.
- Replacing `start_task.py`, worktree/board coordination, checks, archive or `finish_task.py`.
- Using the gh-aw maintenance pilot as the managed-task executor.
- Recording every quick task in the central backlog.

## Decision 1: two task classes, chosen by user/work scope

`managed task` means planned work represented by a Development Backlog issue carrying a managed OpenSpec package. It is intended for non-trivial work, future work, work needing prioritization, or work that may cross sessions/agents.

`quick task` means a small direct request given to an agent for immediate execution. It uses the current dev-platform lifecycle and does not require a central issue/OpenSpec merely for traceability.

Agents do not auto-convert every direct request into managed work. They escalate only when continuing would materially broaden product/architecture/data/compatibility scope.

## Decision 2: the backlog stores planning transport, not an active repository change

While a managed task remains in Backlog, its OpenSpec package stays with the central issue. This avoids accumulating many active `openspec/changes/` directories for work that may never be scheduled soon.

The transport format is versioned. V1 uses one recognizable package marker, one machine-readable JSON manifest, and explicitly delimited artifact blocks. JSON keeps the parser in the Python standard library and avoids adding a YAML dependency solely for transport.

Required v1 manifest fields:

- `version`
- `source_issue`
- `target_repository`
- `change`
- `prepared_against`
- ordered `artifacts`

The importer accepts exactly one current v1 package. Artifact contents are bytes/text between explicit file markers; package text is never executed.

## Decision 3: deterministic importer with a narrow write boundary

Generated repositories receive `scripts/managed_task.py`. The central `dev-platform` source may dogfood the same implementation from its template path or a thin source-repository wrapper; the canonical reusable implementation remains platform-owned template code.

The import command accepts a canonical issue reference (at minimum `owner/repo#number`; URL support may be added if it remains deterministic). It:

1. resolves the current repository root and normalized `origin` identity;
2. obtains validated GitHub CLI/API credentials using existing platform helpers;
3. fetches the issue and comments;
4. locates and parses exactly one supported managed package;
5. validates source/target/change/artifact paths and package completeness;
6. synchronizes/observes the current target state needed for freshness reporting without taking ownership of implementation start;
7. asks the installed OpenSpec CLI to create/inspect the change using the current repository schema;
8. writes only allowed planning artifacts under the resolved change root;
9. records provenance/package revision in a small machine-readable local file associated with the change;
10. runs the repository-supported structural OpenSpec preflight;
11. reports freshness and the next semantic-preflight/apply step, then exits.

It never runs apply, edits implementation code, changes GitHub Project status, or invokes publication.

## Decision 4: current repository identity is a hard safety check

The package target is an `owner/repo` identifier. The importer derives the current target identity from `origin`, normalizing standard GitHub HTTPS/SSH forms. If it cannot prove equality, it fails closed. This prevents importing a valid package into the wrong checkout merely because the change name happens to exist there.

No machine-specific absolute path is stored in the issue package.

## Decision 5: package artifact paths are allowlisted by containment

All imported file paths must be relative planning paths resolved by the current OpenSpec change root. Absolute paths, `..` traversal, `.git` targets, and paths outside that root are rejected before any write. The importer stages content in memory/a temporary area and validates the full package before mutating the change so malformed packages do not leave a half-imported state where avoidable.

## Decision 6: OpenSpec CLI owns scaffold/schema; package owns agreed semantics

The importer does not assume that every project forever has exactly the same artifact layout. It uses the installed OpenSpec CLI/status/instructions supported by the current repository to establish the change scaffold and verify that the package can satisfy the current planning contract.

The package is not permission for the importer to invent missing product semantics. If the schema changed materially, import stops for reconciliation rather than synthesizing a different change.

The coding agent may make strictly formal/schema-compatible adjustments during semantic preflight, but a material change to intent, observable behavior, compatibility or acceptance criteria requires user resolution.

## Decision 7: freshness is evidence, not a blanket SHA lock

`prepared_against` records the target `main` commit ChatGPT inspected. If current synchronized `main` is equal, the package is freshness-aligned. If it differs, the package is marked stale and the agent must inspect relevant current specs/active changes/code before apply.

A different SHA does not itself fail import because unrelated commits should not make a valid product decision unusable. Material semantic conflict is the stop condition.

## Decision 8: idempotency uses provenance and package revision

The importer computes a stable SHA-256 package revision from normalized manifest metadata plus ordered artifact paths/content. After successful import it records at least:

- source issue
- target repository
- change name
- package revision
- prepared-against commit
- import timestamp/version

Re-running the same source/package is a safe verification/resume path. A different package revision must not silently overwrite an existing materialized change. A same-name change with different/no matching provenance is treated as a conflict.

This preserves the source-of-truth transition: after materialization, repository OpenSpec can evolve under normal no-silent-divergence rules without being overwritten from the backlog.

## Decision 9: auth and dependencies reuse platform primitives

No new API key or service is introduced. Reading a private Development Backlog repository reuses validated `gh` authentication already required by platform-owned PR workflows where applicable. If auth is unavailable, intake fails before mutation.

The helper should prefer Python standard library plus existing platform helpers. It shells out only to established tools (`git`, `gh`, `openspec`) through bounded/checked subprocess calls. It must not parse human-readable success text when structured output is available.

## Decision 10: rollout follows ordinary Copier ownership rules

New projects receive the helper and updated guidance from the template. Existing managed repositories receive a reviewed Copier update. Template contract tests and upgrade smoke must include the new managed file so a rollout cannot silently omit the helper.

For mature `harness_mode=project` repositories, managed-task intake remains planning-only and therefore can be offered independently of who owns branch/worktree publication. If an existing repository already owns a colliding `scripts/managed_task.py` or agent-guidance section, normal ownership/conflict review wins; no blind overwrite is permitted.

## Decision 11: bootstrap this first change manually

Issue `lehard/development-backlog#1` defines the importer itself, so it cannot be imported by the yet-nonexistent importer. The first implementation agent may manually create the OpenSpec scaffold with the current CLI and copy this package after validating target/source/freshness. That one-time bootstrap exception must not become the normal documented path after the helper ships.

## Rollback

Rollback removes the generated importer and managed-task guidance through a reviewed platform change/Copier update. Existing repository-local OpenSpec changes remain normal OpenSpec data and are not deleted. Existing backlog issues remain human records; their packages simply cease to have an automatic importer until the feature is restored.

