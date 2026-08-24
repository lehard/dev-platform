# Design: Isolated external agent-runtime adapter

## Decisions

1. **Experimental backend, not new foundation.** DSH is an optional backend behind a Dev Platform-owned boundary. Native Codex/Claude execution remains the default.
2. **Integrate, do not fork.** Use a supported upstream DSH distribution/integration surface selected during implementation preflight. Pin the exact version; do not vendor/copy upstream source as the normal integration mechanism.
3. **Minimal boundary.** Upper layers should need only bounded operations equivalent to start, cancellation, terminal status/result and execution evidence. DSH/Cordis types, session ids, plugin registries and internal event vocabulary stay inside the adapter.
4. **One lifecycle owner.** Dev Platform owns managed task identity, OpenSpec, assigned workspace/worktree, routing decision, verification, publication and final completion. DSH may own internal run/session/tool lifecycle only for one bounded execution.
5. **One owner per safety invariant.** Dev Platform selects the authorized workspace/writer. The runtime may provide OS/process confinement within it. The adapter must report whether containment is proven/partial/unavailable rather than merging ambiguous claims.
6. **No second execution database.** Persist only the existing normalized execution provenance plus the minimum adapter-local state required for one run/recovery. Do not build a parallel tracing/session warehouse in Dev Platform.
7. **Pinned, manually promoted upstream.** Dependency updates are explicit PR/change events: bump exact version, run adapter compatibility tests and bounded smoke, then include in a normal immutable Dev Platform release.
8. **Disabled by default.** No downstream project or ordinary managed task should execute through DSH merely because the adapter is present.
9. **No broad capability migration.** Agent Teams, skills migration, DSH-owned planning and other attractive subsystems are intentionally excluded until the core runtime experiment proves value.
10. **Nested runtime limitations are real evidence.** The existing Codex-in-Codex sandbox-depth near-miss means live adapter smoke must use a host-level/evaluation path that does not confuse nested-product restrictions with DSH correctness.
11. **Coupling budget is architectural.** If supporting DSH requires changes to task-intake/OpenSpec/verification/publication/rollout semantics or leaks DSH-specific public types into them, stop and surface the incompatibility instead of broadening the adapter.

## Runtime evidence

The adapter should translate only bounded facts into the common provenance contract:
- runtime/backend identity and exact version;
- run/execution id when safely available;
- start/end/elapsed;
- terminal result/outcome and cleanup/cancellation;
- usage/token/request evidence where DSH exposes it;
- containment/enforcement status needed by the caller.

Full DSH session logs remain runtime-local forensic evidence and are not copied into the Dev Platform provenance store by default.

## Update model

1. Detect or intentionally select a new upstream version.
2. Update the exact pin in a reviewable change.
3. Run adapter contract/compatibility tests.
4. Run bounded safe smoke against the new version.
5. Release through normal immutable Dev Platform release/rollout only after checks pass.

No automatic upstream update reaches production.

## Implementation preflight (2026-08-24)

The official `deepseek-ai/deepseek-harness` repository is still marked as a
developer preview with compatibility-breaking changes expected.  The supported
distribution surfaces observed during implementation are:

- `@deepseek-ai/dsh` `0.1.1-rc.2`, which exposes the product CLI and a one-shot
  headless profile;
- `deepseek-harness-sdk` `0.1.1rc1`, which installs the exact same-version
  `deepseek-harness-runtime-bin` wheel and exposes a synchronous Python API over
  JSON-RPC stdio;
- an MIT license in the upstream repository and both selected Python
  distributions.

The adapter uses the Python SDK because it is the smallest published surface
that exposes structured start, bounded terminal result, session events and
deterministic process cleanup without importing Cordis or DSH session types
into platform lifecycle code.  Both the configured and installed SDK/runtime
versions must equal `0.1.1rc1`; a mutable branch, `latest`, compatible range or
different same-family version is rejected.

## Adapter boundary and current containment limit

The platform-owned module exposes runtime-neutral capability, request, handle,
terminal-result, timing, usage and cleanup dictionaries.  The DSH import and
event vocabulary remain private to that module.  A run is launched in a new
process group so cancellation and abnormal cleanup can terminate and reap the
SDK worker together with its bundled runtime child.

The initial `observation` profile mounts no model-facing filesystem, shell,
subagent, MCP or other write-capable tool.  It passes the assigned workspace as
the SDK `cwd` and keeps session state under an explicitly selected directory,
but reports containment as not applicable rather than claiming a sandboxed
writer.

The pinned SDK can compose DSH's native workspace sandbox internally, but its
public `RunResult` does not expose the selected sandbox runner or its
`full`/`partial` enforcement fact.  Persisted tool presentation also omits that
successful canonical value.  Therefore this iteration refuses a
`workspace-write` request before launch with an actionable capability result.
It must not infer containment from configuration intent, parse unstable human
text, or broaden task-intake/routing/publication contracts to recover a DSH
internal fact.  Enabling write-capable execution requires a later exact-version
compatibility event whose supported API supplies provable enforcement evidence
or a separately proven platform containment wrapper.

## Relationship to execution-efficiency evidence

`lehard/development-backlog#68` reached `main` in `lehard/dev-platform#312`
before this change entered final verification.  Its canonical representation
is `execution.efficiency`: platform-owned timing carries
`started_at`/`ended_at`/`elapsed_ms` with `source: platform` and
`status: measured`, while every runtime usage field is a
`{value, source, status}` measurement over the fixed runtime-neutral field set.

The adapter reuses that vocabulary and helper implementation from
`model_routing.py`; it does not retain its earlier DSH-local partial/status
shape.  DSH `inputTokens` is the runtime's disjoint fresh-input count,
`cacheReadTokens` maps to cache-read, `outputTokens` maps to output, and one
root `assistant/message` event is one countable model request.  A token field is
measured only when every counted request supplies a non-negative integer for
that field; partial/malformed samples remain canonical `unknown`.  Canonical
`input_tokens` and `total_tokens` remain unknown because the pinned supported
surface does not expose those exact aggregate identities.  Cancellation and
failure records still carry platform timing with unknown usage.

Comparative pilots and runtime selection remain blocked regardless of adapter
capability.
