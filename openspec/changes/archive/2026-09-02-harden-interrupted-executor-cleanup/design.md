# Design: Extend the existing process-group boundary

## Decisions

1. Keep `start_new_session`, process-group identity and existing ownership records as the only writer-control mechanism.
2. Install scoped signal handling only while a delegated writer is live, restore prior handlers afterward, and route interruption through common cleanup.
3. Cleanup sends bounded termination/escalation signals to the group and proves absence before release.
4. The abnormal receipt classifies signal interruption, timeout and other launcher failure while reporting only bounded progress/diff state.
5. No automatic retry or second writer is allowed from ambiguous state.
