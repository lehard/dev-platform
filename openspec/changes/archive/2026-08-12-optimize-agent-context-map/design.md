# Design: bounded root agent context with progressive repository guidance

## Design goal

Keep the root agent file useful when it is the only repository context loaded, without paying the cost of carrying every specialized workflow in every task. The root file becomes an index plus invariant layer; executable mechanics remain scripts, behavioral contracts remain OpenSpec, and detailed operating guidance remains repository documentation.

This is a context-architecture refactor, not a process-policy rewrite.

## 1. Classify guidance by loading frequency

Before editing, inventory the meaningful directives in the current central and template root guidance and classify each into one of two classes.

### Always-on root guidance

A directive belongs in root `AGENTS.md` only when an agent normally needs it before it can safely decide what detailed context to load. At minimum the root map should contain:

- the contract/source-of-truth model (`AGENTS.md`, current specs, active changes, code, docs and machine-local coordination state);
- the distinction between discuss, explicit managed-task fixation, quick execution and execution of an existing managed task;
- no-silent-divergence and material-conflict stop rules;
- the primary supported start/check/finish entrypoints rather than their internal algorithms;
- concise safety invariants around protected main, worktree/scope isolation where applicable, required verification and non-destructive handling of other agents' state;
- platform-owned versus project-owned context boundaries;
- a short navigation section mapping common task types to the canonical detailed documents.

The root file may contain another rule only when preflight can explain why delaying that rule until a linked document is read would create a material correctness or safety risk.

### Just-in-time detailed guidance

Detailed algorithms, recovery behavior, option matrices, provider-specific routing mechanics, long command sequences and lifecycle internals should live in the appropriate existing docs and be loaded when the task reaches that concern. Candidate areas include managed-task/OpenSpec workflow, worktree/publication lifecycle, provider/model routing, release/adoption behavior and process-friction completion details.

Do not create a second catch-all file that merely moves the monolith elsewhere. Prefer existing thematic docs; add a new thematic document only when no current canonical destination is coherent.

## 2. Preserve one canonical cross-agent entrypoint

`AGENTS.md` remains the vendor-neutral repository-wide entrypoint and the location that tells an unfamiliar agent how to discover the rest of the contract. `CLAUDE.md` and any future Hermes/tool adapter must not duplicate the full ruleset. They may import/reference `AGENTS.md` or add only truly tool-local mechanics that cannot be expressed in the vendor-neutral contract.

Do not add `.hermes.md` as a second process source of truth merely because Hermes supports such a file. If Hermes later requires a thin compatibility adapter, that is a separate integration decision and must preserve this canonical layering.

Module-level `AGENTS.md` remains the preferred place for subtree-specific rules. Project-domain and stack-specific rules remain project-owned rather than being promoted into the platform root.

## 3. Make moved guidance discoverable

Removing text from root is safe only when agents can deterministically find the detailed contract when needed. The root map should therefore provide stable navigation by concern, for example:

- task execution / worktrees / publication -> agent workflow guidance;
- OpenSpec authoring, verification and archive -> OpenSpec workflow guidance;
- provider-local executor selection -> model-routing guidance;
- project-specific engineering rules -> project-owned rules/documentation;
- central platform adoption/release/rollout concerns -> the corresponding central durable docs.

Exact wording and link layout are an implementation choice, but navigation must use repository-relative stable paths and avoid prose that depends on one agent product's UI.

## 4. Prove semantic preservation during migration

The implementation must create temporary verification evidence that traces each meaningful directive from the pre-change root file to either:

1. an explicit retained always-on root invariant; or
2. one canonical detailed destination that is linked/discoverable from the new root map.

This trace is migration/verification evidence, not a new permanent competing policy document. Any directive with no justified destination is a blocker until its ownership is resolved.

Existing tests and lifecycle behavior remain authoritative. In particular, managed-task intake, OpenSpec verification/archive, protected publication, worktree containment, provider routing and the active friction/retrospective completion contract must not change observable semantics as a side effect of wording relocation.

## 5. Enforce a bounded root-guidance budget

Add a mechanical contract test for both central source and rendered platform-owned downstream guidance. The check should enforce:

- a hard maximum line/size budget chosen during preflight close to the agreed 80–120 line operating target;
- required structural/navigation anchors for the always-on categories above;
- thin tool-adapter behavior where platform-owned adapters are rendered;
- successful render for all supported factory profiles.

The exact hard limit should be based on the final meaningful content rather than gaming line breaks, but it must be strict enough that future features cannot casually append whole workflows to root guidance. A change that truly needs more always-on context must deliberately update the bounded contract and its justification instead of silently expanding it.

## 6. Verify risk-proportionally

Verification depth follows the risk of the change, not the file paths it touches. A semantic-preserving compaction of instruction, documentation and template text is verified with focused evidence:

- text integrity — every meaningful directive traced to a retained root invariant or one canonical destination;
- structure and anchors — required always-on categories still present;
- destinations and links — every navigation target exists and resolves;
- render — all supported factory profiles render within the bounded contract;
- contract checks — the focused guidance tests plus semantic OpenSpec review.

An unrelated full software regression suite is not required solely because instruction/documentation/template files changed. Where the change also touches executable surfaces, run the checks relevant to those surfaces. Where a directive's meaning is intentionally changed rather than shortened or relocated, reconcile OpenSpec first and add targeted behavioral evidence for the affected runtime/provider; a model's self-report is not evidence.

The risk-proportional selector itself is separate work (`reduce-platform-test-cycle-time`, backlog issue #27) and is not implemented here.

## 7. Reconcile active changes before editing shared guidance

`adopt-gh-aw-process-automation` is active and changes the completion/friction contract that generated agent guidance must communicate. Preflight must compare the latest active delta before moving that section. If its final semantics have changed since this package was prepared, preserve the current active contract and relocate only its presentation layer.

Other active changes touching `AGENTS.md`, template guidance or documentation ownership discovered at execution time must be reconciled the same way. A material contradiction returns for resolution; it must not be hidden by selecting one copy of the wording.

## Non-goals

- changing Hermes execution or worktree integration;
- changing model/provider routing policy;
- redesigning Development Backlog, OpenSpec or publication lifecycle;
- optimizing test runtime;
- introducing a general autonomous doc-gardening system;
- replacing repository docs with skills or MCP servers.
