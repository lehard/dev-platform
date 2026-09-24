# Design: Base-bound candidate generation

## Inputs and identity

The receipts, archived child heads and their source branches remain immutable inputs. The new candidate is bound to exact current main as its `base`. When a child head does not descend from that base, derive its independent delta from the merge base of current main and the child head; dependent children still use the preceding verified child head. Record every exact delta base in the manifest. A stale branch, missing common base, ambiguous overlap, or application conflict fails closed.

Only a replayed candidate gets a base-bound generation suffix in its worktree and branch. The original fixed-name candidate remains available for audit and is never reset, removed or reused for a different manifest. The manifest digest includes the generation and base. Resume accepts only the exact generation and commit sequence.

## Local contract

If `.dev-platform.toml` is ignored in the integration checkout, the candidate receives a same-content local copy before validation. A tracked config is already carried by Git. An existing mismatched or unexpected candidate config blocks; no user or sibling file is overwritten.

## Publication and risk

The existing full validation and protected PR publisher remain authoritative. Git-backed tests cover moved main before initial PR, replay conflict, deterministic resume, and local contract behavior. The original child branches and older candidate are not modified. The exact merged PR proof still owns child/parent Done and local main reconciliation.

The `recover` subcommand is the explicit terminal entrypoint for this exceptional path. It requires a clean shared integration checkout on main, exact ordered child receipt paths, and a Requirement identity. It assembles against that main head, selects the manifest's generation-specific branch, composes, then calls the existing full-check protected publisher. The normal supervisor remains unchanged; a moved-main recovery uses this explicit command rather than taking over its prior candidate.
