# Migration trace: root guidance directives

Verification evidence for `optimize-agent-context-map` (tasks 1.2 and 4.1). Every meaningful directive in the pre-change root guidance is traced to one of:

- **root** — retained as an always-on invariant/map entry in the new root file;
- a **canonical destination** document, discoverable from the root map's navigation table.

Pre-change baseline: `AGENTS.md` at 131 lines and `template/AGENTS.md.jinja` at 206 lines, both at `6d2629db8b5f4e6ed6dbdcdaa5dba8a0ddd14d8a`. No directive was dropped.

## Central `AGENTS.md`

| Pre-change section | Retained in root | Canonical destination |
| --- | --- | --- |
| Contract model | `## Sources of truth` (full list, plus "no second backlog" and the safety-over-artifact rule) | [docs/engineering/openspec-workflow.md](../../../docs/engineering/openspec-workflow.md) |
| No silent divergence | invariant: update the artifact *first* | openspec-workflow.md |
| Selective goal definition | invariant: selective, creates no durable artifact, plus link | [docs/engineering/agent-workflow.md](../../../docs/engineering/agent-workflow.md) |
| Managed/quick intake, four intents | `## Task intents` with both entrypoints and the canonical-after-import rule | agent-workflow.md |
| Backlog Project state reconciliation (`In review`/`Done`/`block`/`resume`) | — | agent-workflow.md |
| Formal repair vs material conflict | invariant: managed contract conflicts stop | agent-workflow.md |
| Quick-task expansion stop rule | invariant | agent-workflow.md |
| Verification before archive, PASS receipt, lifecycle debt | invariant: verification is not a checkbox count | openspec-workflow.md |
| Never fabricate a receipt | invariant | openspec-workflow.md |
| Central dogfood lifecycle commands | `## Entrypoints` (start/route/status/archive/finish) and the "not complete until MERGED" rule | agent-workflow.md |
| Scope discipline | `## Ownership` | agent-workflow.md |
| Platform capabilities/profiles | `## Ownership` (one line) | agent-workflow.md |
| Delegated write containment | invariant: no path mutates integration state | [docs/engineering/model-routing.md](../../../docs/engineering/model-routing.md) |
| Provider-local model routing | invariant: routing is a required gate, user does not choose, containment must be proven | model-routing.md |
| Release safety | invariant: never `dev-platform@main`, refs append-only | [docs/release-policy.md](../../../docs/release-policy.md), [docs/managed-rollout.md](../../../docs/managed-rollout.md) |
| Validation commands | `## Entrypoints` (retained verbatim) | agent-workflow.md |
| OpenSpec dependency policy | `## Ownership` (do not vendor generated skills) | openspec-workflow.md |
| Friction routing | invariant: resolve the friction checkpoint | agent-workflow.md |

Release safety needed no new destination: `docs/release-policy.md` already carried immutable tags, `managed-projects.json` states, least-privilege App tokens and fail-closed rollout, and `docs/managed-rollout.md` already carried the private-key and force-push rules.

## Generated `template/AGENTS.md.jinja`

Destinations are repository-relative in the rendered project (`docs/engineering/...`).

| Pre-change section | Retained in root | Canonical destination |
| --- | --- | --- |
| Contract model | `## Sources of truth` including the agent-board caveat | openspec-workflow.md |
| OpenSpec and no silent divergence | invariants (divergence, checkbox count, receipt) | openspec-workflow.md |
| Selective goal definition | invariant plus link | agent-workflow.md |
| Managed/quick intake, four intents | `## Task intents` | agent-workflow.md |
| Start-of-task synchronization | `## Entrypoints` with doctor/start behavior | agent-workflow.md `## Start of task` |
| Shared workspace permissions | — | agent-workflow.md `## Shared workspace permissions` |
| Profile blocks | `## Profile` (per-profile paragraph retained) | agent-workflow.md `## Profiles` |
| Multi-agent scope claims | `## Profile` (`--scope`, `WAIT`, advisory globs) | agent-workflow.md |
| Worktree hygiene commands | invariant: other agents' state is off limits | agent-workflow.md `## Worktree hygiene` |
| Delegated write containment | invariant | model-routing.md `## Delegated write containment` |
| Provider-local model routing | `## Profile` (routing gate, no user choice, proven containment) | model-routing.md |
| Validation and publication | `## Entrypoints` plus the `publish_mode` block | agent-workflow.md `## Publishing`, `## Local-heavy, cloud-final verification` |
| Checks are never bypassed; no Git courier | invariant | agent-workflow.md |
| Platform release and CI updates | one line under the navigation table | agent-workflow.md `## Platform release and CI updates` |
| Friction and promotion | invariant: friction checkpoint | agent-workflow.md `## Friction and promotion` |
| Completion checklist | invariants: verification order, friction checkpoint, report blockers | agent-workflow.md `## Completion` |

## Reconciliation with active changes

`adopt-gh-aw-process-automation` is active and owns the friction/completion contract in `platform-lifecycle` and `agentic-maintenance`. Its deltas are spec-level and do not edit either root guidance file, so there is no wording conflict. Its observable semantics are preserved here: friction stays machine-local with automatic sanitized fingerprinted issue upsert, process issues remain evidence-only (no managed task, OpenSpec, PR or code change), routing failure stays durable and non-blocking, and the completion friction checkpoint remains a required completion invariant — retained in root rather than relocated, because completion must not depend on having loaded a linked document.

No other active change touches `AGENTS.md`, `template/AGENTS.md.jinja` or documentation ownership.

## Ownership note

`AGENTS.md`, `CLAUDE.md` and (for `harness_mode=project`) `docs/engineering/agent-workflow.md` and `openspec-workflow.md` are `_skip_if_exists` in `copier.yml`. Relocating detail between those files does not change that boundary: as before this change, existing downstream projects keep their own copies and platform upgrades do not rewrite them. `docs/engineering/model-routing.md` remains platform-owned in both harness modes, and no new downstream file was introduced, so no project-owned path became platform-owned.

## Mechanical guard

`tests/test_root_guidance_contract.py` enforces the resulting contract: a 120-line hard budget for central `AGENTS.md` and for every profile render, the six required navigation anchors, resolvable navigation links, thin tool adapters, and absence of the relocated detail signatures. The rendered check runs the real Copier render of all three supported profiles from a VCS-free copy of the working tree.
