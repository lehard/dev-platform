## Context

`dev-platform` already has a deliberate intake boundary: discussion does not create backlog state; explicit fixation creates one managed Issue/OpenSpec package; quick tasks execute without that ceremony. OpenAI's curated `define-goal` is intentionally narrower than a planner: it improves objective quality and explicitly avoids durable planning artifacts. That makes it suitable as an intake refinement layer rather than a replacement for OpenSpec.

## Goals / Non-Goals

**Goals:** improve fuzzy-task formulation; preserve source-of-truth boundaries; distribute reusable guidance to downstream projects; degrade honestly when goal tooling is unavailable.

**Non-Goals:** mandatory goals for all work, a persistent goal database, a second implementation plan, automatic backlog creation, or Sol/Luna critic orchestration.

## Decisions

- Place goal refinement conceptually before OpenSpec/managed authoring, not inside implementation or publication lifecycle.
- Keep activation selective: explicit goal-backed intent or material ambiguity in outcome/evidence. Do not add ceremony to concrete quick tasks.
- Adopt the official quality semantics rather than copying its entire runtime state machine into platform code.
- Do not vendor external/generated skill content by default. During implementation preflight, inspect the then-current supported Codex skill/runtime mechanism and choose the smallest reusable integration compatible with template/Copier rollout.
- If native goal state is unavailable, allow a clearly transient natural-language fallback meeting the same quality bar; never emulate a persistent `get_goal/create_goal` state that the runtime cannot actually provide.
- Keep model routing orthogonal. A future critic-loop change can consume a good goal, but this change must be independently useful and safe.

## Implementation preflight (2026-08-12)

The current supported Codex environment is `codex-cli 0.135.0`, where `codex features list` reports `goals` as stable and enabled. Current official guidance exposes durable goal execution through `/goal`, while agent runtimes may expose equivalent native `get_goal`/`create_goal` tools. The curated `define-goal` skill remains available in Codex vendor imports and supplies the quality semantics, but it is not present in the installed skill surface for this session.

The smallest reusable integration is therefore agent-contract guidance, distributed through the existing AGENTS/Copier path. The guidance names the native capability portably (`/goal` or runtime-native goal tools), limits durable native state to explicit goal-backed requests, requires active-state inspection before native creation when that operation is available, and explicitly distinguishes a transient natural-language refinement from native goal state. A fuzzy request being prepared for managed authoring receives transient refinement, not an implicit durable `/goal`. No skill content, runtime adapter, or durable goal file is added.

This approach is consistent with the current managed-task and OpenSpec contracts: refinement happens before authoring, while the resulting Issue/OpenSpec package remains the only durable implementation contract. It does not overlap the active `adopt-gh-aw-process-automation` change, which concerns process automation rather than request formulation.

## Risks / Trade-offs

Overusing goal refinement would add latency and ceremony, so the contract explicitly preserves direct execution for concrete tasks. Depending directly on an evolving external skill API can also make the platform brittle; implementation therefore binds to supported capability at preflight rather than inventing a permanent internal API prematurely.

## Verification

Exercise at least one fuzzy non-trivial intake and one concrete quick-task intake in rendered template guidance/tests. Verify that managed authoring still produces the existing Issue/OpenSpec package without an extra durable goal artifact, and that unsupported goal runtime handling cannot report false native goal state. Run relevant template contract, OpenSpec lifecycle and Copier/render smoke checks.
