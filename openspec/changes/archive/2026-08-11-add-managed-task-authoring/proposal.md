## Why

Source backlog issue: `lehard/development-backlog#3`  
Prepared against: `lehard/dev-platform@8f9652d92ddb3e48937685c209873f1928935bdb`

The Development Backlog now has a deterministic intake side: a coding agent can receive an existing managed issue, import its `managed-openspec:v1` package, preflight the materialized OpenSpec change, and then continue through the normal repository lifecycle. What is still missing is the symmetric authoring side when the product/design discussion happens directly with Codex or Claude Code instead of in ChatGPT.

Today the same human intent has different outcomes depending on the conversation surface. In ChatGPT, an explicit “зафиксируй” can produce a central Issue plus a ready OpenSpec package. In a repository coding session, generated `AGENTS.md` only describes importing an already-created managed issue and escalating an oversized quick task. It does not define how Codex/Claude should turn an agreed discussion into the same central managed-task representation. The repository configuration also does not yet tell an agent which backlog repository, project label, or default priority to use.

The platform should make managed-task creation a shared repository capability rather than a ChatGPT-only convention. The user-facing semantics should be consistent across ChatGPT, Codex, and Claude: discussion alone creates nothing; an explicit fixation command creates the managed task and OpenSpec package; implementation begins only after a separate execution command.

## What Changes

- Extend the managed-task capability with deterministic **authoring** in addition to the existing import path.
- Add a standard authoring entrypoint to generated repositories, implemented as a `managed_task.py create` subcommand or an equivalently clear single helper surface. It receives the already-prepared human issue content and OpenSpec artifacts, performs safety/configuration/duplicate checks, creates the central Issue with configured labels, publishes exactly one `managed-openspec:v1` package, and stops.
- Add Development Backlog configuration to the project contract: backlog repository, project label, and default priority. Target repository remains derived from the current GitHub `origin` identity so it cannot silently drift from the checkout being discussed.
- Update root and generated `AGENTS.md` so discussion, fixation, quick work, and execution of an existing managed task are distinct operations. “Зафиксируй”, “добавь в бэклог”, “создай задачу” and equivalent explicit intent for a non-trivial change mean: consolidate the accepted decision, inspect relevant current repository context, check for an obvious duplicate, prepare the OpenSpec package, create the managed task, then STOP before implementation.
- Keep `AGENTS.md` as the canonical cross-agent contract. `template/CLAUDE.md.jinja` continues to import `@AGENTS.md`; managed-task rules are not duplicated in Claude-specific instructions. Codex consumes the same repository contract.
- Reuse the existing `managed-openspec:v1` transport format. Authoring must not introduce a second package schema that the importer then has to translate.
- Preserve source-of-truth boundaries: before scheduling, the central Issue plus package is the managed planning handoff; after later import/materialization, repository-local OpenSpec becomes the canonical implementation contract under the existing rules.
- Keep authoring non-executing. Creating the managed task must not create a persistent active `openspec/changes/<change>` in the target repository, run apply/start/finish, dispatch an agent, mutate GitHub Project workflow state, or otherwise begin implementation.
- Deliver the capability to new repositories through the normal template and to existing managed repositories through reviewed Copier rollout.

## Capabilities

### Modified Capabilities

- `managed-task-intake`: expand the capability from one-way import to a complete managed-task handoff boundary with deterministic authoring and import, while retaining the existing `managed-openspec:v1` contract.
- `project-factory`: generated repositories carry the backlog authoring configuration, helper, and canonical agent guidance required for the same user-facing managed-task behavior across Codex and Claude.

## Platform / rollout scope

This is universal platform behavior for repositories that participate in Development Backlog, not a workflow-profile-specific execution feature. `light`, `standard`, and `multi-agent` repositories may all author a managed task because authoring creates planning state in GitHub and does not own branch/worktree/publication behavior.

The change affects new renders and existing managed-project updates. Expected downstream-managed surfaces include `AGENTS.md`, `.dev-platform.toml`, `scripts/managed_task.py`, related engineering guidance/tests, and `CLAUDE.md` only insofar as tests must preserve its existing canonical `@AGENTS.md` indirection.

## Compatibility and active-change boundaries

The existing import contract and package parser remain backward-compatible. A task created by the new authoring path must be consumable by the current `managed_task.py` import semantics without translation or a format bump unless implementation discovers an unavoidable incompatibility and updates this OpenSpec first.

`durable-publication-recovery` owns GitHub-backed publication observation/reconciliation. `add-central-dogfood-lifecycle` in Development Backlog #2 owns a runnable start/finish adapter for the central source repository. `adopt-gh-aw-process-automation` owns bounded friction/process-maintenance automation. This change owns none of those responsibilities: authoring ends after the central managed task and planning package are created.

The change may touch root/generated agent guidance that #2 also touches. If #2 is materialized or implemented concurrently, the implementation must reconcile those shared guidance edits rather than overwrite either contract.

No new cloud service, daemon, API key, or parallel task database is introduced. Existing authenticated GitHub CLI/API access and installed OpenSpec tooling remain the dependency boundary.
