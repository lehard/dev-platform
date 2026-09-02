# Design: Selective interrogation inside existing goal/OpenSpec refinement

## Decisions

1. **Capability mechanics come from #87.** This change owns refinement behavior only; shared identity/provenance/opt-in/materialization/update/remove stay in the optional-capability foundation.
2. **Selective trigger.** Use only for materially ambiguous or explicitly domain-heavy work; concrete tasks proceed normally.
3. **Evidence-first.** Repository/document evidence is searched before turning factual ambiguity into a user question.
4. **Human questions are product choices.** Ask only when the remaining ambiguity can materially change intended outcome and cannot be safely resolved from available evidence.
5. **No parallel docs.** Do not require `CONTEXT.md`, ADR/status ledgers or a second plan; accepted decisions update the existing proposal/spec/design artifacts.
6. **OpenSpec remains canonical.** After materialization, the managed OpenSpec package is the sole implementation contract.
7. **Upstream as pattern.** `grill-with-docs` informs the interrogation approach but does not become an authoritative runtime workflow dependency.
8. **No invented requirements.** The capability can identify missing choices but cannot silently choose new product requirements for the user.
