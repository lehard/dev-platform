# Optional engineering capabilities

Optional engineering capabilities are reusable development behaviors that compose with, rather than rename, `light`, `standard`, and `multi-agent` workflow profiles. They never add application runtime dependencies, production credentials, origin permissions, or write authority.

## Source and selection

Each descriptor in `dev-platform/capabilities/<id>.toml` is the provider-neutral source of truth. It declares identity, purpose, kind, invocation/visibility intent, ownership, provenance hash, safety boundary, dependencies and lifecycle policy. The referenced instruction file is hash-checked; external content must be pinned and is never fetched from a mutable upstream at runtime.

`dev-platform/capabilities.toml` is project-owned opt-in state. An empty `enabled` list means no provider skill surface, extra agent context, tool runtime, or dependency is materialized. Copier delivers the default file once and preserves later project choices.

## Lifecycle

Use the discoverable management entrypoint:

```bash
python3 scripts/capability_manager.py list
python3 scripts/capability_manager.py enable <id>
python3 scripts/capability_manager.py update <id> --change-kind material
python3 scripts/capability_manager.py audit
```

It also exposes `create`, `remove`, `show`, `validate`, `sync`, and `eval-decision`. `create` accepts a reviewed descriptor plus sibling instruction file in the Dev Platform source through a managed task; downstream projects may only choose released descriptors. `remove` disables a capability and removes only its marked derived files. The current adapters materialize `auto+explicit` instruction-only and isolated tool-backed capabilities as native skill Markdown for Claude and Codex. Unsupported invocation intents are reported truthfully rather than emulated by a second router.

Capability authoring always performs structural validation and emits an eval decision. Metadata-only changes are `skip-with-reason`; material or trigger changes are `blocked/unavailable` until the provider-neutral eval runner from Development Backlog #79 is available. Ordinary use never depends on a live eval.

## Delivery

The manager, descriptors and guidance are Copier-managed platform surfaces. Fresh renders and reviewed Copier updates are deterministic; an immutable platform release produces ordinary rollout PRs for managed projects. Project-owned harnesses retain their lifecycle implementation.
