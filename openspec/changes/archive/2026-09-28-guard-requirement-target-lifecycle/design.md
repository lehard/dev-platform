# Design: Requirement target support boundary

## Support evidence

The target repository is the authority for managed execution support. Local intake reads the current target checkout, requiring `[development_backlog]` routing, enabled managed OpenSpec/Git lifecycle capabilities, managed child and Requirement entrypoints, and a usable protected publication lifecycle. A configuration table or routing label alone does not prove support. Existing project factory operator integration remains an explicit opt-in for downstream repositories whose operator configuration is external. Dev Platform source checkout is supported through its source lifecycle adapter and local configuration. A malformed or unreadable target config fails with an actionable support error.

Connected intake reads the target default branch for committed lifecycle evidence. If the target intentionally leaves `.dev-platform.toml` untracked, the existing operator-declared Project parameters are accepted only with explicit target-side operator integration evidence and the same supported managed entrypoints; parameters alone are not the opt-in. If the connected surface cannot prove support, it refuses fixation and names the target checkout route that can establish it.

## Gates and failure

Create checks support before Issue creation. Start and supervisor checks bind the Issue's exact target repository to the current checkout and fail before ordinary pre-authoring or child execution for an existing unsupported Requirement. The failure identifies absent evidence and a supported path: configure/opt the target into the managed lifecycle, or use its own supported local workflow outside a Dev Platform Requirement. No automatic retargeting or manual terminal shortcut occurs.

Terminal reconciliation rechecks the parent Issue's exact target against the current checkout and retains exact child package, archived verification, merged publication and Project evidence checks. It refuses an empty child set and cannot infer delivery from a manually closed parent.

## Compatibility

Keep routing configuration and operator-managed downstream parameter derivation unchanged. The support predicate is reusable by local and connected adapters; tests cover source checkout, rendered managed target, operator opt-in target, and arbitrary operator repository with valid routing but no managed lifecycle.
