## Decisions

- **Entry.** Requirement scenarios enter after pre-authoring with authored fixture bundles. ADD approval is a human decision and stays outside a scenario; the scenario starts at `requirement_intake.py`, child linking and `execute_requirement.py advance`.
- **Backlog.** Requirement Issues live in the sandbox with its own Project and `project:` label.
- **Post-merge.** The runner calls the same `work-next` kinds the post-merge runner calls, from the sandbox checkout. No LaunchAgent is installed.
- **Coverage list.** It lives in `docs/engineering/live-scenarios.md`, as a map and not a backlog. `close-abandoned-delegation` is listed with its reason: Codex only, and Codex scenarios are excluded.

## Risks

Sandbox composition full checks are small, so only tool availability and gate order are proven, not the duration of the real suite.
