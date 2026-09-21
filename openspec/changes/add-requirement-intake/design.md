# Design: Human-facing Business Requirement object

## Scope

Requirement authoring/linkage/aggregation only. `orchestrate_pre_authoring.py` (#129), `add_intents.py`, `project_evidence.py`, and the managed OpenSpec/GitHub delivery lifecycle are unchanged and remain the only implementation authority.

## Requirement representation

An ordinary Development Backlog Issue, not a new store:

- Label `type:requirement` (created with `gh label create --force`, idempotent).
- Body: fixed markdown sections -- `## Outcome`, `## Context` (optional), `## Acceptance evidence` (optional), `## Target repository`, `## Exclusions` (optional) -- plus one machine-readable children block:

```text
<!-- requirement-children:start -->
- [ ] owner/repo#N
<!-- requirement-children:end -->
```

- Stable identity: `requirement-<issue-number>`, matching `orchestrate_pre_authoring.py`'s `ID_RE`-compatible slug shape (`add_id`/`--id` already require `[a-z][a-z0-9-]{1,63}`).

No proposal/design/tasks/technical decomposition is required or accepted at Requirement authoring time.

## Entrypoint surface

`scripts/requirement_intake.py` (thin, composes existing primitives; no new persistence):

- `create --repository OWNER/REPO --title T --outcome-file F --target-repository R [--context-file] [--acceptance-file] [--exclusions-file]`: renders the body, creates the Issue via the same `gh issue create` / `github_cli_env` path `managed_task.py` already uses, ensures the label, returns the reference.
- `start --requirement OWNER/REPO#N [--base-dir DIR]`: fetches the Issue body (`managed_task.fetch_issue`), extracts `## Outcome`, writes it to `<base-dir>/<slug>/requirement.md`, and calls `orchestrate_pre_authoring.init(requirement_id=slug, requirement_file=..., target_repository=<parsed ## Target repository>)`. From here the main agent drives `orchestrate_pre_authoring.py status`/`record-decision` exactly as #129 already defines; this command only performs the one-time bridge.
- `link-child --requirement OWNER/REPO#N --child OWNER/REPO#M`: idempotently inserts `- [ ] owner/repo#M` into the children block (no duplicate), ensures/attaches `type:internal-change` on the child, and appends a `Requirement: owner/repo#N` back-reference line to the child's body if not already present.
- `aggregate --requirement OWNER/REPO#N`: parses the children block, calls `managed_project_status.observe(root, source_issue=child)` for each entry, and derives one label from the real statuses:
  - no children yet -> `pre-authoring`;
  - any child status unreadable/`None` -> `unknown` (fails closed, never assumed);
  - all children `Done` -> `Done`;
  - any child `Blocked` -> `Blocked`;
  - otherwise -> `In progress`.

  This is pure read-through: no status is written back to the Requirement, no new state machine is introduced, and a child's authoritative status stays owned by the existing Development Backlog Project exactly as it is today for a directly-authored managed task.

## Main-board visibility

Two labels are the entire mechanism: `type:requirement` (human-facing) and `type:internal-change` (technical child, hidden from the primary view by an explicit Project filter). Mutating a saved Project view/filter is not provable through the current authentication (same category of gap already recorded for other Project-view actions in this platform); this change ships the labels and documents the exact one-time manual filter the owner adds once, rather than silently skipping main-board hygiene.

## What the OTHER chat (ChatGPT Project protocol) needs to activate this

Not activated in this change. The exact, minimal delta for that chat to apply later:

1. Replace the current `"зафиксируй"` handler (`docs/engineering/chatgpt-project-protocol.md`'s direct-to-OpenSpec authoring path) with: author a Requirement via `requirement_intake.py create` instead of a managed OpenSpec bundle.
2. After Requirement authoring, hand off to `requirement_intake.py start` (bridges into #129's pre-authoring), then let the main agent drive `orchestrate_pre_authoring.py status` to completion.
3. When pre-authoring reaches `complete`, author the internal managed OpenSpec change(s) from each ready handoff envelope through the existing `execute_managed_task.py`/`managed_task.py create` path exactly as today, then call `requirement_intake.py link-child` once per resulting Issue.
4. Nothing else in the existing quick-task or direct managed-task/OpenSpec path changes.

## Explicitly out of scope

Installation Model v1, standalone/embedded distribution, any change to `orchestrate_pre_authoring.py`'s stage logic, any new backlog/status/Project schema beyond the two labels above.
