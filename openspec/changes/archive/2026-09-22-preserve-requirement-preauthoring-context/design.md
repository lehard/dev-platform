# Design: Canonical complete Requirement binding

## Boundary

Requirement intake will parse the known business sections into one canonical, deterministic local representation. The representation is written only inside the ignored pre-authoring directory and is bound by the existing orchestrator digest/state mechanism. The target repository remains part of that binding even though it is also an explicit orchestrator argument.

## Invalidation behavior

On resume, intake fetches the Requirement Issue again and compares the canonical representation with the saved binding. If it is unchanged, existing snapshot/ADD/intents/handoffs remain eligible for their existing freshness checks. If it changes, intake must not silently reuse artifacts derived from the old business meaning. It will invalidate local downstream derived artifacts from the earliest affected pre-authoring boundary and reinitialize/rebind safely; it must never overwrite canonical OpenSpec that has already been materialized.

## Handoff behavior

The complete representation is supplied as bounded business context to intent decomposition/handoff. It does not duplicate implementation decisions: ADD and intents continue to own the technical delta until the managed OpenSpec package is materialized.

## Compatibility and risks

Existing Outcome-only pre-authoring directories need a safe, explicit migration/rebuild path rather than a false equivalence claim. Tests cover old-state handling, content changes, and unchanged resume. The main risk is treating formatting-only Issue edits as semantic changes; canonical parsing normalizes section boundaries and whitespace before digesting, while every changed section value remains significant.
