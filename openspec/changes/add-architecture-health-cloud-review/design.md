# Design: Architecture Health Review gains a bounded cloud execution job

## Boundary

The new workflow is a thin GitHub Actions/gh-aw wrapper around Architecture Health Review's existing instruction content. It does not re-implement or fork that content; the cloud job reuses the same instructions a local interactive session would use. If literal reuse inside a gh-aw prompt requires adapting how that content is presented for non-interactive batch execution, that adaptation stays textual/prompt-level and must not change what the review evaluates.

## Execution model

Following agentic-maintenance's accepted pattern:

- Engine: Codex, authenticated via the existing repository Actions secret (`OPENAI_API_KEY`).
- Tools: read-only GitHub/repository tools only, scoped to what a structural/architecture review needs; no `shell`, no `git`, no unrestricted external network.
- Safe outputs: one bounded declared output for a summary artifact. The combined durable-report format is out of scope for this change; a minimal safe output (for example a workflow-run summary or a scoped comment) is sufficient here.
- Guardrails: declared `timeout-minutes`, `max-ai-credits`, and `max-turns`, mirroring the conservative bounds already accepted for `weekly-process-backlog-review`.

## Compatibility and rollback

Existing local/interactive invocation of architecture-health-review is unchanged; this change only adds a new, additive cloud trigger. Removing or disabling the new workflow file fully reverts to today's local-only behavior; no data or state migration exists.

## Risks and mitigations

- Risk: a batch/non-interactive Codex run may reason differently than an interactive session over the same instructions. Mitigation: the job stays strictly read-only/advisory with no write authority, so a lower-quality batch run only produces a weaker advisory summary, never an unsafe mutation.
- Risk: uncontrolled cost from a new recurring cloud job. Mitigation: explicit runtime/AI-credit guardrails per the accepted agentic-maintenance pattern, central-pilot-only scope.
