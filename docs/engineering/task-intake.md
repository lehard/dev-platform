# Managed task intake

This is the canonical, platform-owned contract for turning a user request into
work. `AGENTS.md` remains the short repository map; project/domain rules remain
project-owned. Read this document before authoring or executing non-trivial
work.

## Intent boundary

- **Discuss**: inspect, design and compare. Do not create durable Backlog state.
- **Fix / add to Backlog**: an explicit recording request (for example
  `зафиксируй`, `добавь в бэклог`, `создай задачу`) authors or updates the
  managed package and stops. It never starts implementation or changes Project
  status.
- **Quick execution**: a small, clear, bounded change may use normal task
  execution without a Backlog Issue or ceremonial OpenSpec change.
- **Fresh non-trivial execution**: an explicit request to implement, fix,
  build, or otherwise execute material work creates or reuses its managed task,
  starts that exact task, and only then begins implementation.
- **Existing managed task**: start the supplied Development Backlog Issue.

User wording is evidence of the current intent, not a magic keyword. Direct
execution does not require a second `зафиксируй` instruction. A fixation-only
request remains authoring-only unless the same request also clearly authorizes
execution.

## Evidence-first execution

Use repository evidence to narrow work before broad reading or unnecessary
human interruption. If the relevant file, symbol, owner, or contract is not
known, search first; then read only the likely evidence-bearing files needed to
make the next decision or act safely. If the canonical path is already known,
read it directly rather than performing a ceremonial search.

Resolve factual ambiguity from repository evidence when the repository can
answer it. Ask the user when a material product, intent, or scope choice remains
rather than turning a repository lookup into a question. Once enough evidence
exists to act safely inside the agreed scope, proceed instead of continuing
open-ended exploration by default.

## Commands

Prepare the normal managed authoring bundle (`manifest.json`, `issue.md`, and
the declared OpenSpec artifacts). For authoring-only use:

```bash
python3 scripts/managed_task.py create --bundle <directory>
```

For a fresh, non-trivial execution request use the one composed entrypoint:

```bash
python3 scripts/execute_managed_task.py --bundle <directory> --scope "<files/modules>"
```

It composes the existing authoring checks with `start_managed_task.py`; it does
not create another backlog, dispatcher, package format, or state machine. A
retry reuses the authoring receipt or exact existing Issue, then resumes the
same managed start identity. Candidate overlap remains an explicit decision:
review it and pass `--confirm-distinct` only when the scopes are genuinely
separate.

For an already supplied managed Issue use:

```bash
python3 scripts/start_managed_task.py owner/repo#N
```

Managed start performs read-only package intake, creates/reuses the task
checkout, materializes the canonical local OpenSpec only there, and reconciles
the Development Backlog item to `In progress`. It stops before implementation.
After materialization, the local OpenSpec is canonical; the Issue is human-
facing provenance rather than a second implementation plan.

## Escalating quick work

Keep quick work quick. If inspection reveals material behavioral,
architectural, compatibility, data-contract, cross-session, or scope impact —
or if a full active OpenSpec change is needed to govern the work — stop further
implementation and enter managed intake first. Do not create a normal active
OpenSpec change as a substitute for managed provenance.

The ordinary terminal lifecycle rejects an active OpenSpec change that lacks
managed provenance. This does not affect genuine quick work with no active
OpenSpec. Legacy/manual states need a reviewed recovery that records their real
source identity; never fabricate an Issue, delete work, or bypass the guard.

## Existing managed repositories

This document is platform-owned and arrives through normal release rollout.
Project-owned root `AGENTS.md` keeps local rules, but must include the stable
reference inserted by the rollout migration. The migration is additive and
marked; it does not replace project/domain or module-level instructions.
