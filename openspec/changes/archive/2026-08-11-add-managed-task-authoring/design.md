## Context

`managed-openspec:v1` currently defines a clean planning handoff from Development Backlog into a repository. `template/scripts/managed_task.py` can read the central Issue/comments, validate target and package shape, create the repository-local OpenSpec scaffold through the installed OpenSpec CLI, preserve provenance/idempotency, and stop before implementation. Generated `AGENTS.md` describes this import path plus quick-task escalation.

The authoring side is currently outside the platform. ChatGPT Project instructions know where the central backlog lives and which `project:*` label to use, but repository coding agents do not. The generated `.dev-platform.toml` contains workflow/OpenSpec/promotion configuration but no Development Backlog authoring configuration. `CLAUDE.md` already has the desirable architecture: it imports `@AGENTS.md` and explicitly treats that file as canonical.

The problem is therefore not a new planner or executor. It is a missing deterministic adapter from an already-agreed repository conversation to the same central managed-task representation that ChatGPT can create.

## Goals

- Make “зафиксируй” mean the same managed planning operation in ChatGPT, Codex, and Claude Code.
- Keep semantic planning model-driven while making GitHub/package mechanics deterministic.
- Keep Development Backlog a queue of intentionally managed/future work, not a log of every quick change.
- Reuse the existing `managed-openspec:v1` format and later import path unchanged.
- Avoid persistent target-repository OpenSpec state until the user actually schedules the task for execution.
- Deliver the feature through normal Project Factory/Copier mechanisms.

## Non-goals

- Watching GitHub Project `Ready` or dispatching workers.
- Mutating GitHub Project statuses.
- Automatically executing a task after authoring it.
- Replacing the existing importer or creating a second package format.
- Moving quick tasks into Development Backlog.
- Maintaining separate semantic instructions for Codex and Claude.
- Building a general-purpose project-management service or semantic duplicate-resolution system.

## Decision 1: one human task protocol across conversation surfaces

The repository contract distinguishes four intents:

1. **Discuss** — analyze, design and inspect without creating backlog state merely because the discussion is substantial.
2. **Fix / add to backlog** — for a non-trivial accepted change, create the managed Issue and OpenSpec package, then stop.
3. **Quick execution** — a small direct implementation request may use the existing quick-task lifecycle without central backlog/OpenSpec ceremony.
4. **Execute existing managed task** — an explicit Development Backlog issue is imported/preflighted and then implemented through the existing lifecycle.

The agent must use meaning, not a brittle exact Russian keyword parser. The listed phrases are examples of unambiguous user intent, not command tokens that the helper itself must interpret.

## Decision 2: AGENTS.md remains canonical; Claude remains an indirection

Managed-task semantics belong in the platform-generated repository contract because they affect every coding agent. `AGENTS.md` is therefore the canonical location. `CLAUDE.md` keeps the existing small `@AGENTS.md` bridge and must not grow a copied task protocol. Codex receives the same rules from `AGENTS.md`.

This preserves one contract when future task semantics change and avoids subtle Codex/Claude divergence.

## Decision 3: model prepares content; helper performs deterministic publication

A language model is well suited to consolidate the accepted discussion, inspect relevant specs/active changes/code, choose the OpenSpec delta content and draft the human issue body. It is a poor place to repeatedly reconstruct GitHub API calls, label rules and transport delimiters.

The authoring helper therefore accepts prepared content through a supported local interface and owns:

- configuration resolution;
- target-repository identity;
- current preparation commit;
- bounded duplicate lookup;
- priority/project labels;
- creation of the central Issue;
- insertion of the new issue number into package provenance;
- deterministic `managed-openspec:v1` serialization/publication;
- cleanup/failure behavior if the publish sequence cannot complete safely.

The exact CLI input shape (for example body/artifact files, a temporary authoring bundle, or a structured manifest) should be chosen during implementation for the smallest dependency-light interface. It must avoid shell-quoting large model-generated Markdown and must not require arbitrary command execution from package content.

## Decision 4: authoring configuration belongs in project configuration

The backlog repository, project label and default priority are stable project-process metadata and should be rendered with the repository rather than repeated in prompts. A dedicated section in `.dev-platform.toml` (or an equivalently explicit schema-owned configuration block) is preferred.

Conceptually:

```toml
[development_backlog]
repository = "lehard/development-backlog"
project_label = "project:<project>"
default_priority = "P2"
```

The exact schema key names may follow existing configuration conventions, but the three values must be explicit and validated. Target repository is intentionally not duplicated there: it is resolved from normalized `origin` so authoring cannot accidentally post a task for a different checkout.

`add-central-dogfood-lifecycle` (Development Backlog #2) landed during implementation. Its explicit source `.dev-platform.toml` is therefore extended with the same `[development_backlog]` table; no second root configuration source or lifecycle adapter is introduced.

## Decision 5: reuse v1 transport and do not leave an active change

Authoring produces the same package the importer already understands. It must not create a second “authoring package” format.

The agent still needs current OpenSpec context to prepare a correct package. The implementation may validate the provided artifact set against current OpenSpec tooling/schema using a safely contained temporary mechanism, but successful authoring leaves no persistent `openspec/changes/<change>` directory in the target repository. The actual active change is materialized later by the importer when the user schedules execution.

This preserves the important distinction between a potentially large Backlog and the small set of currently active repository changes.

## Decision 6: duplicate checking is bounded and conservative

The helper should query open central tasks scoped by configured project/target using deterministic GitHub search/API access, then provide enough candidate metadata for a conservative decision. It may automatically reject an exact/unambiguous duplicate, but should not use an opaque model-free similarity threshold to merge product scopes.

If overlap is ambiguous, the agent returns the candidates and asks the user whether to update an existing task or create a separate change. This mirrors the ChatGPT Project rule and prevents both obvious spam and accidental task conflation.

## Decision 7: GitHub issue creation is transactional enough to fail visibly, not magical

GitHub Issue creation and comment/package publication are separate remote mutations. The helper cannot make them truly atomic with GitHub REST primitives. It must therefore make partial state explicit and recoverable rather than silently creating an issue with no package or duplicating the issue on retry.

Implementation should use a stable authoring marker/idempotency identity derived from target/change/prepared content or another deterministic receipt so a retry can find/reconcile an issue it created before a later package-publication failure. The exact receipt representation is an implementation decision, but retries must not create duplicate central tasks solely because the first process stopped after Issue creation.

No remote rollback by deleting a human-visible Issue is required; a partial publish should be reported and safely resumable.

## Decision 8: authoring receives an explicit local bundle

The standard helper interface is `managed_task.py create --bundle <directory>`. The
bundle contains a small `manifest.json` with the managed-task title, change name and
ordered artifact paths, a Markdown `issue.md` body, and the declared artifact files
at those relative paths. This keeps model-authored Markdown out of shell arguments
and gives the helper one contained filesystem root to validate before it contacts
GitHub.

The helper resolves the target repository and preparation SHA itself. It validates
the bundle against the current OpenSpec schema in a temporary change root, removes
that root on every outcome, and only then creates or resumes the central Issue.
When its bounded target/project lookup returns existing non-identical candidates,
the invoking agent must explicitly confirm that the scopes are distinct before
creation; an exact same-change candidate is always rejected. This preserves a
model-owned semantic scope decision without allowing silent duplicate creation.

## Security and authentication

Authoring reuses the existing validated GitHub CLI/API credential path. It does not print tokens or raw credential material. The private backlog repository may require authenticated access; inability to read/search/create there is an actionable authoring blocker.

The OpenSpec package is Markdown planning content, never executable input. Existing artifact-path containment rules remain applicable to any local validation/materialization step.

## Upgrade / rollback

The feature is platform-owned and distributed through the existing Project Factory/Copier release path. Existing repositories receive configuration/guidance/helper changes through reviewable upgrades.

Rollback is a normal platform release/revert. Existing authored `managed-openspec:v1` issues remain valid because the transport format and importer are not changed. Removing the create entrypoint simply removes local authoring convenience; it does not corrupt already-created tasks.
