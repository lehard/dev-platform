# Design

Reuse the current issue body as the durable streak state. Read the target repository's authoritative platform version markers from its default branch and compare against the last failed release. Require a coherent version record at or beyond the failed release before closing. Preserve an unreadable issue or project state as open; report a bounded diagnostic. Add an operator-triggerable reconciliation path so it does not depend on a later rollout.

The existing stale-rollout maintenance workflow already has the operator registry and project App token. Add a daily scheduled event and run alert reconciliation for each managed project on that event. Keep manual dry-run limited to stale-PR planning; manual apply can also reconcile alerts. The scheduled event never applies stale-PR supersession.

The reconciliation job's repository token needs `issues: write` to close the existing tracker issue. Keep `contents: read`; the separate project App token continues to own project and PR access. Update the CI guardrail assertion for these exact scoped permissions.

Risk: version-only evidence may overstate recovery if a project restored a different path. Validate the existing coherence contract used by rollout no-op before closing.
