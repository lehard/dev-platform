# Bounded prototype

Use this capability only when managed work carries **material product, UI or
technical uncertainty** that available evidence cannot settle and a small
**observable experiment** would resolve faster than more analysis. It runs one
disposable experiment and returns a decision plus bounded evidence. It is not a
mandatory step, not a place to build a feature, and not a second task lifecycle.

Do not run it for a task whose outcome and approach are already clear enough to
author or execute: a concrete bounded change, an already-specified behavior, a
mechanical correction, or a bug fix with an established cause and approach. A
clear task gets no prototype ceremony. If an apparently clear task turns out to
hide a consequential unknown that an experiment would settle, stop and run this
pass before implementing on a guess.

This capability is independently authored. It is informed by common "spike" and
"tracer bullet" practice; no upstream skill is vendored or fetched at runtime.

## 1. State the experiment before starting

Write down, in bounded form:

| Field | Required content |
| --- | --- |
| Question | The single decision the experiment must inform. |
| Options / hypotheses | The 2+ concrete alternatives or the falsifiable claim under test. |
| Bounds | Declared time, iteration and cost limits for the experiment. |
| Success signal | What observation would distinguish the options. |

If you cannot name the question and a distinguishing signal, an experiment is not
the right tool — return to analysis or ask the user.

## 2. Work in an isolated area only

Run the experiment in one of:

- a temporary throwaway workspace (for example a scratch directory or a disposable
  branch/worktree that is never published), or
- a prototype area the project has explicitly declared for this purpose.

The experiment MUST NOT change production source, dependency manifests,
credentials, CI, or managed task/lifecycle state. It MUST NOT be given
credentials, production write access, sensitive data, or permissions beyond the
current scope; if it would need any of those, refuse and report the boundary
instead of working around it. All existing repository, network and data safety
rules stay in force.

## 3. Run within the declared bounds

Stop when the success signal is observed, when the declared bounds are reached,
or when it becomes clear the evidence will be insufficient. Do not extend the
bounds silently to chase a result. Record the stop reason.

## 4. Record the decision, not a plan

Capture a bounded decision record:

- Question, options/hypotheses and declared bounds (from step 1).
- Observation — what actually happened, in bounded form: no transcript, no
  secrets, no sensitive payloads.
- Decision, or the remaining uncertainty plus the safest bounded interpretation
  if the experiment did not resolve it.
- Evidence reference — a path or link to the temporary artifacts.

Put this record where the managed task keeps its working notes or, for managed
OpenSpec work, fold the resolved decision into the artifact it belongs in
(`proposal.md`, delta specs, `design.md`, `tasks.md`). Do not create a new
`CONTEXT.md`, ADR ledger, status log, issue, progress file, or second backlog.

## 5. Clean up; do not promote prototype code

Delete the temporary workspace or prototype-area contents by default once the
decision is recorded. Retention is allowed only when it is explicitly requested
and policy-compatible, and retained artifacts are still not production source.

Prototype code is disposable. It MUST NOT be copied into production
automatically. When the decision calls for real implementation, that work enters
the ordinary managed OpenSpec lifecycle and is written fresh against the
contract — the prototype is reference and evidence, not a starting commit.

## Representative shapes

- **UI variant:** two candidate layouts for a settings screen, built as static
  throwaway mockups, compared against a declared usability signal; the decision
  ("layout B — fewer steps to the primary action") and screenshots path are
  recorded, both mockups are deleted, and the real screen is implemented through
  managed intake.
- **Technical spike:** a falsifiable claim that a streaming parser can hold the
  10k-row page under 50ms; a scratch benchmark tests it within a 2-hour bound;
  the measured result and script path are recorded, the scratch dir is removed,
  and the parser change is proposed normally.
- **Not applicable:** "add a GET /health endpoint that returns 200 and the build
  SHA" — the outcome is fully specified; no experiment, implement directly.
- **Refused:** "prototype the payment flow against the live Stripe account to see
  what breaks" — needs production credentials and real charges; refuse and report
  the boundary.
