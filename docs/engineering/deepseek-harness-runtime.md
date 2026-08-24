# Experimental DeepSeek Harness runtime adapter

Dev Platform includes an optional integration-capability adapter for
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness). It is a
developer-preview experiment, not a production executor, routing choice, or
managed-project default.

## Current supported surface

Implementation preflight on 2026-08-24 selected the official Python SDK rather
than the product CLI:

- distribution: `deepseek-harness-sdk==0.1.1rc1`;
- bundled runtime: `deepseek-harness-runtime-bin==0.1.1rc1` (installed as the
  SDK's exact same-version dependency);
- transport: JSON-RPC over a bundled runtime subprocess;
- upstream license: MIT;
- tested profile: `observation` only.

The separate npm CLI was `@deepseek-ai/dsh` `0.1.1-rc.2` at preflight time. It
is not the adapter dependency: its one-shot stdout/exit surface is less useful
for structured result, usage and cancellation evidence than the official
Python SDK.

The SDK's published runtime wheels currently support Linux x86_64/aarch64 and
macOS 14+ arm64. Other hosts receive an actionable `incompatible` capability
result; the adapter never falls back to `master`, `latest`, a source checkout,
or another release.

## Opt-in and capability check

Rendering or updating Dev Platform does not install DeepSeek Harness and does
not select it. New project configuration includes:

```toml
[experimental_runtime.deepseek_harness]
enabled = false
sdk_version = "0.1.1rc1"
profile = "observation"
```

Existing projects that predate the section use the same disabled defaults.
Inspect capability without enabling a run:

```bash
python3 scripts/deepseek_harness_adapter.py capability
```

For a temporary experiment, create a dedicated virtual environment and install
the exact pin from `requirements/deepseek-harness.txt` in a rendered project or
`template/requirements/deepseek-harness.txt` in the central source repository.
Do not add this dependency to platform bootstrap or ordinary CI.

An actual run requires an explicit `--enable-experimental` flag (or a deliberate
local configuration enablement), an assigned workspace, and a session directory
inside that workspace:

```bash
python3 scripts/deepseek_harness_adapter.py run \
  --enable-experimental \
  --workspace /absolute/assigned/worktree \
  --session-root /absolute/assigned/worktree/.claude/dsh-sessions \
  --prompt "Return a concise observation."
```

Ambient `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL` are inherited by the SDK
worker but are never placed in argv or result evidence.

## Boundary and ownership

The platform module owns capability checks, the exact-version gate, assigned
workspace/session-root validation, worker process-group lifecycle, timing,
cancellation, bounded result normalization and usage extraction. DSH owns only
its internal runtime/session/model loop for that one process.

Dev Platform remains the sole owner of managed task identity, OpenSpec,
worktree assignment, routing, verification, publication, release, rollout and
friction/calibration. DSH session logs remain adapter-local runtime evidence;
they are not another task database or completion authority.

DSH/Cordis types and event names are confined to
`scripts/deepseek_harness_adapter.py` and the private Cordis profile. No
task-intake, routing-policy, verification, publication or rollout public type
depends on them.

## Containment status

The initial `observation` profile exposes no model-facing filesystem, shell,
subprocess, subagent, MCP, skill, workflow, goal, or other write-capable tool.
Containment is therefore reported as `not-applicable`, not as a sandbox claim.

The pinned SDK can compose DSH sandbox plugins internally, but its public
`RunResult` does not attest which sandbox runner executed or whether enforcement
was `full` versus `partial`. Successful persisted tool presentation also omits
that canonical enforcement value. Consequently `--profile workspace-write`
fails closed before launch with `containment_unavailable`. Configuration intent
or human-readable output is not accepted as proof.

A host-level smoke uses a temporary workspace and local keyless model fixture,
checks startup/run/result/usage/cleanup, cancels and reaps a second process
group, proves workspace-write refusal, and compares the protected integration
checkout before/after:

```bash
python3 scripts/deepseek_harness_adapter.py smoke --enable-experimental
```

If the pinned wheel is unavailable on the host, the smoke returns `blocked`
with the exact capability diagnostic instead of fabricating success.

## Evidence dependency and non-goals

The adapter emits the canonical runtime-neutral `execution.efficiency` shape
delivered by `lehard/development-backlog#68` / `lehard/dev-platform#312`. Its
platform timing uses the shared measured timing helper, and every usage field
uses the shared `{value, source, status}` vocabulary. DSH `inputTokens` maps to
disjoint `fresh_input_tokens`, `cacheReadTokens` to `cache_read_tokens`, and
`outputTokens` to `output_tokens`. Counted root assistant-message events are
retained only as the runtime-local
`deepseek_harness_assistant_message` counter: the adapter does not claim they
are one-to-one model requests. A token field is measured only when every counted request
contains a valid value; partial or malformed evidence stays `unknown`, never
zero. `input_tokens` and `total_tokens` remain unknown because the pinned DSH
surface does not expose those exact aggregate identities. No second DSH-local
usage schema is retained. Its token fields are comparable only inside a
compatible DSH/provider generation, not directly with another runtime.

This change does not authorize comparative evaluation, automatic runtime
selection, a production switch, Agent Teams, skill migration, or removal of
native Codex/Claude execution.

## Exact-version update procedure

1. Select an explicit published SDK/runtime version and re-check the official
   integration API, wheel platforms, repository/package license, cancellation,
   result/usage fields and containment evidence.
2. Update the exact config constant and optional requirements pin together. Do
   not use a compatible range, `latest`, `master`, or an automatic promotion.
3. Update the private profile only if the pinned runtime requires it, keeping
   DSH/Cordis semantics inside the adapter layer.
4. Run keyless contract/compatibility tests and the host-level bounded smoke.
   A write-capable profile remains refused unless the supported surface proves
   its real enforcement boundary.
5. Run normal Dev Platform semantic verification, archive, PR, immutable
   release and rollout. Installing a new adapter version still must not change
   default routing or downstream execution.
