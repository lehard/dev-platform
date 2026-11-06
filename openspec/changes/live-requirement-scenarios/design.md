## Decisions

- **Entry.** Requirement scenarios enter through the real pre-authoring chain, from depth selection to authored handoffs, then `requirement_intake.py`, child linking and `execute_requirement.py advance`. Only the snapshot worker results and the bundles are fixture input, and the ADD approval is recorded under a scenario identity: the approval is a human decision and a scenario proves only its path.
- **Backlog.** Requirement Issues live in the sandbox with its own Project and `project:` label. The runner adds children to the Project through `managed_project_status.py ensure` when `advance` reports it maps to no items: the sandbox Project has no auto-add workflow.
- **Parallel children.** Sibling children share the integration manifest, so the board reports overlap on every parallel `finish`. The scenario acknowledges it through `agent_board.py acknowledge`, the documented entrypoint.
- **Snapshot.** The platform suite is dropped from the sandbox. Composition full checks use the platform set when `template/scripts` exists, so the overlay supplies one fixture test group.
- **Repaired contribution.** Review binds the head, so a contribution repaired by the queue passes review again before it merges.
- **Post-merge.** The runner calls the same `work-next` kinds the post-merge runner calls, from the sandbox checkout. No LaunchAgent is installed.
- **Coverage list.** It lives in `docs/engineering/live-scenarios.md`, as a map and not a backlog. `close-abandoned-delegation` is listed with its reason: Codex only, and Codex scenarios are excluded.

## Risks

Sandbox composition full checks are small, so only tool availability and gate order are proven, not the duration of the real suite.
