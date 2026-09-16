# Proposal: Bounded pilot of System One / Jev as an atomic-judgment decision layer

## Why

Dev Platform already executes managed tasks, collects verification/evidence, and manages lifecycle, but there is no separate, cheap semantic layer of atomic judgments between "an agent finished a run" and "the platform allows the next action." System One / Jev proposes an architecture where a model does not generate free text but answers a set of narrow typed questions (boolean/choice/score with confidence), and a deterministic policy decides the resulting action. This change runs one bounded offline pilot to evaluate that architectural pattern -- and Jev as one candidate backend for it -- without creating a vendor dependency or changing the production managed-task lifecycle.

## What Changes

- Define a provider-neutral atomic-judgment contract for evaluating a completed managed agent run. The contract does not depend on Jev-specific public types; a Jev/System One adapter is one interchangeable backend behind it.
- Establish a first bounded taxonomy of roughly 15-25 judgments (for example: task/spec completion; scope respected vs. suspicious scope expansion; missing required artifact/change; sufficient test evidence; regression risk; security/sensitive-surface touch; migration/config/release impact; suspiciously large or unrelated diff; verification contradiction; human-review recommendation; retry vs. review vs. accept).
- Where a judgment can be established by a strictly deterministic check (tests, file existence, exit status, exact version, changed paths), that check is the source of truth; the model is scored only on genuinely ambiguous semantic properties.
- Run the same canonical input for each replay case through up to three arms: (1) a deterministic/rule baseline where applicable, (2) the existing cheap general-purpose model adapter, (3) Jev, only when its API/runtime is reachable.
- Replay at least 5 already-completed representative managed tasks, using their preserved task/spec/diff/verification evidence, including at least one bounded bug/recovery case and one capability/process-change case.
- Record an independent reference verdict for each labelable judgment, or an explicit `unknown/not-labelable`; the benchmark never invents ground truth.
- Produce one pilot report ending in exactly one decision: `proceed-to-shadow`, `watch-only`, or `reject-for-now`.

This change does not authorize live gating, auto-merge based on model confidence, replacing existing verification, a mass benchmark of all past tasks, training a custom model, changing R1/R2/R3 routing, or downstream rollout.

## Success criteria

- A versioned judgment schema and bounded initial taxonomy exist.
- At least 5 historical replays run on identical canonical input across the compared backends.
- A ground-truth/reference verdict for each labelable judgment is recorded independently of the backend under evaluation.
- Dangerous false-allow/false-safe errors are reported as their own metric, never folded into an average accuracy figure.
- Cost/latency comparison never substitutes for a correctness judgment.
- Ambiguous or unsupported provider fields remain `unknown` rather than inferred.
- No Jev-specific type or SDK leaks above the adapter boundary.
- The production managed-task lifecycle is unchanged after the pilot.
- The report contains exactly one of the three decisions plus a concrete activation criterion for the next step.

## Out of scope

Live gating; auto-merge driven by model confidence; replacing existing verification; a mass benchmark across all historical tasks; training a custom model; changing R1/R2/R3 routing; downstream rollout.
