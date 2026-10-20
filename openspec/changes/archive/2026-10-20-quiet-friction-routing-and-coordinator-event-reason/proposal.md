## Why

Every `start`, `doctor` and `finish`/`advance` run calls `agent_friction.py route-pending` synchronously with a 15-second timeout (`agent_doctor.retry_friction_routing`, `finish_task.run_friction_route_pending_retry`). When GitHub routing is slow or a pending event cannot route, every ordinary command waits and prints the same warning again (lehard/dev-platform#486, lehard/dev-platform#512). Routing is telemetry: the accepted contract only requires that a pending event stays retained for a later retry, not that each lifecycle command performs that retry.

Coordinator lifecycle events reach the process issue stream without saying what happened: the routed body shows only the generic observation (for example "required platform validation failed"), while the reason and the candidate stay in the local evidence field that is deliberately never published. lehard/dev-platform#176 accumulated 31 identical comments with no detail.

## What Changes

- `agent_doctor` (and therefore `start`) and `finish_task` (and therefore `advance`/`finish`) no longer invoke `route-pending`; they neither wait on GitHub routing nor print a routing warning. Locally retained events stay retained and are retried by the explicit `python3 scripts/agent_friction.py route-pending` command (operator or Process Health Review). The existing local friction review status line in doctor is unchanged.
- Coordinator events carry two structured fields: `reason` (bounded, sanitized one-line cause) and `candidate` (`task` branch, `number` when a PR exists, `head`). The publication coordinator (`publication_queue.emit_friction`) fills them from the transition detail and candidate; `finish_task` fills them for `lifecycle-validation-failure` from the failure descriptor and the current branch/head. Missing reason or candidate at the producer fails explicitly with a named error.
- `agent_friction.py record` accepts `--reason` and `--candidate-task/--candidate-number/--candidate-head`; `append_coordinator_event` accepts `reason` and `candidate`.
- The router renders `- Candidate:` and a `### Reason` section. A coordinator-category event without a reason or candidate is not routed: its route is recorded as `withheld` naming the missing field, it is not retried, and `route-pending` reports the count.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `platform-lifecycle`: friction routing is no longer retried inside ordinary lifecycle commands; routed coordinator events carry reason and candidate, and faceless ones are withheld.

## Impact

`template/scripts/agent_doctor.py`, `template/scripts/finish_task.py`, `template/scripts/agent_friction.py`, `template/scripts/publication_queue.py`, `template/scripts/integration_contour.py` (sink pass-through), docs for friction routing, tests and the regenerated platform manifest. Ships to downstream through the normal release.

## Non-goals

Changing high-signal friction rules or retrospective composition; root-cause dedupe, auto-close or auto-triage (sibling Requirements); repairing or closing existing comments on lehard/dev-platform#176; adding a background routing daemon.
