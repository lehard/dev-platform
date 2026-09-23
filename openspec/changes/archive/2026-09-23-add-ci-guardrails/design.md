# Design

Use a pinned Ruff invocation with E9 and F811/F821/F822/F823: syntax-class failures, duplicate definitions, undefined names, invalid export names, and local binding before assignment. Baseline F821 and F823 findings in agent_friction.py and requirement_intake.py must be corrected before enabling the gate. Put configuration in the repository and expose one local command so CI invokes the same check. Scope checks to maintained Python source and tests, with exclusions only for documented generated or historical files if baseline evidence requires them.

Workflow permissions remain GitHub-native YAML. The stale-rollout reconciler uses a separate GitHub App token for downstream writes; its GITHUB_TOKEN needs only contents: read even in the reconcile job. Audit each platform-owned workflow and set the narrowest token scopes at workflow or job level; jobs that use GitHub App tokens still need only the GITHUB_TOKEN scopes actually consumed. Add job-level timeouts sized for observed workload and guarded against the default six-hour ceiling. Apply equivalent explicit token and timeout limits to the Copier-managed downstream workflow templates, including the project CI and process-label helper. Existing projects receive these limits through reviewed Copier updates. Keep generated gh-aw lock files generated from their source documents.

## Risks and mitigations

- Too broad a lint rule set may cause unrelated cleanup: start with an explicit small rule set and measure baseline findings before finalizing.
- Too narrow workflow permissions may break release or rollout: trace each API operation and preserve required write scopes; validate in PR CI.
- Timeouts may terminate legitimate long jobs: size from recent run durations with headroom and verify cloud runs.
