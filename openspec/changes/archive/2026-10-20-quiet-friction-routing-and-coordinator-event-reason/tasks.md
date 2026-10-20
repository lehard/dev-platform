## 1. Lifecycle commands

- [x] 1.1 Remove `retry_friction_routing` from `template/scripts/agent_doctor.py` and its call.
- [x] 1.2 Remove `run_friction_route_pending_retry` from `template/scripts/finish_task.py` and its call.

## 2. Coordinator event reason and candidate

- [x] 2.1 `agent_friction.py`: `record --reason/--candidate-task/--candidate-number/--candidate-head`, `append_coordinator_event(reason=, candidate=)`, coordinator category set, explicit validation.
- [x] 2.2 `publication_queue.emit_friction`: pass reason and candidate; empty detail raises `QueueError`; sink pass-through in `integration_contour.default_friction_sink` and durable event reconstruction.
- [x] 2.3 `finish_task.record_lifecycle_friction`: pass reason from the validation descriptor and candidate branch/head.
- [x] 2.4 Router: render candidate and reason; withhold faceless coordinator events; `route_pending` reports and skips `withheld`.

## 3. Docs and tests

- [x] 3.1 Document explicit `route-pending` retry and coordinator event fields in the friction docs.
- [x] 3.2 Tests: doctor/finish do not call `route-pending`; coordinator event routed body contains reason and candidate; faceless coordinator event is withheld and not retried; empty detail raises.
- [x] 3.3 Regenerate the platform manifest; run required validation, semantic verification and developer handoff.
