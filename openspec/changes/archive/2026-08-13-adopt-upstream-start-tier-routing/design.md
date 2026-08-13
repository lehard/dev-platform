# Design: Upstream start-tier routing v2

## Context

Current routing treats task difficulty, risk and assurance too similarly and spends strong-model context to decide whether strong execution is necessary. The platform also now has two useful evidence sources that did not exist when v1 was designed: rich upstream OpenSpec authoring/scouting and truthful bounded execution provenance being completed by #5.

## Decisions

### 1. Author a recommendation, not a concrete model

Managed-task authoring records a provider-neutral start recommendation after the normal bounded targeted repository inspection. The durable record contains no Claude/OpenAI model ID. The Issue title exposes only the abstract tier prefix for quick human selection on the board.

Initial production policy:

- `R2` = balanced default.
- `R3` = frontier only with a concrete hard trigger.
- `R1` = economy semantics reserved but disabled until a later evidence gate.

The exact minimal persisted fields are implementation-owned, but the record must preserve at least the recommendation, rubric version, task family/category, routing confidence, assurance, effort hint and any frontier trigger/rationale needed to audit the decision.

### 2. Frontier selection is trigger-based

`R3` is allowed only when additional reasoning capability is plausibly outcome-changing. Valid trigger classes are bounded to:

- unresolved architecture choice after planning/scouting;
- materially unknown diagnosis likely to require cross-cutting reasoning;
- weak objective verification combined with high consequence;
- novel cross-system interaction with no established repository pattern;
- trustworthy execution history showing comparable R2 work regularly escalates;
- a previous substantive balanced attempt that failed for reasoning/diagnostic reasons.

Diff size, number of files, public visibility, blast radius and failure cost alone are not frontier triggers. Those signals may increase assurance or effort while leaving execution at R2.

### 3. Tier, effort and assurance are independent

The platform must be able to represent combinations such as `R2 + high effort + high assurance`. Runtime-specific effort vocabulary remains replaceable configuration/provenance. Assurance controls verification/review expectations, not the executor tier by itself.

### 4. Execution performs a freshness check, not duplicate routing

After materialization, the initial executor checks whether the authored OpenSpec still matches current repository state and whether any new frontier trigger has appeared. It either confirms the authored recommendation or escalates. It does not re-run a broad subjective scoring exercise solely because runtime execution has started.

Downgrading below the authored tier is not required in v2 core. Escalation preserves current task state and verification evidence.

### 5. Strong-parent delegation becomes secondary

A user may start an R2 task directly on the configured balanced provider model. If a task is accidentally opened on a strong model, existing provider-local delegation may still down-route when safe. Strong parent is no longer a mandatory entrypoint or architectural requirement for every managed task.

### 6. One provenance path

Routing v2 extends/reuses the routing/execution record completed by #5. Do not create a new run database, transcript warehouse or telemetry state machine. Future calibration consumes truthful outcomes from this same evidence base.

## Risks and mitigations

- **Upstream recommendation is wrong:** runtime freshness check and bounded escalation remain mandatory.
- **Correlated error because the same planner writes OpenSpec and tier:** frontier hard triggers are explicit, executor independently checks current repo state, and verification remains authoritative.
- **Repository drift between authoring and execution:** freshness check occurs after materialization against current specs/code.
- **Under-routing costs more after retries:** escalation is bounded; outcome provenance must retain failed substantive attempts rather than hiding them.
- **Over-routing remains invisible:** future calibration uses aggregate outcomes and optional sampled replay, not unsupported counterfactual claims.
- **Model lineup changes:** only abstract tier is durable; provider/model mapping remains configuration.
- **Parallel conflict with #5:** implementation does not start until #5 has completed/landed; then reconcile the final provenance schema instead of guessing it here.
