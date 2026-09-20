# Architecture Health Review

Use this capability only when a human asks for an architecture health review, asks to assess a named architectural concern, or explicitly requests alternative-design analysis for a consequential decision. It is an advisory, read-only review; it does not start a refactor.

## Review boundary

1. Record the target repository, the full immutable revision (`git rev-parse HEAD` or the explicitly supplied revision), the reviewed paths, and exclusions before making findings. Do not report against a moving branch name alone.
2. Read the applicable repository guidance, accepted architecture decisions, relevant tests, and recent history only as needed to bound the review. Prefer a named subsystem or demonstrated change hotspot; do not scan the whole repository by default.
3. Inspect code and caller/test use at each candidate location. A file name, line count, import count, or a single adapter is a lead, not evidence of an architectural defect.

## Evidence lenses

Use these lenses without reducing them to a universal score:

- **Module and interface depth:** identify what callers must know, including invariants, ordering, errors, configuration, and performance expectations. A deep module concentrates useful behaviour behind a small interface; a shallow one may expose nearly as much knowledge as it hides.
- **Locality and coupling:** identify whether one change or defect must be understood or duplicated across multiple locations, and show the callers or dependencies involved.
- **Boundaries and leakage:** identify where internal detail, policy, or ownership crosses an interface and whether that coupling is intentional and enforced.
- **Seams and adapters:** distinguish a useful seam from speculative indirection. One adapter is normally only a hypothesis; evidence of genuinely varying implementations or environments makes it a stronger seam.
- **Repeated abstractions:** compare repeated code or wrappers with their callers. Apply the deletion test: if deleting the abstraction merely removes complexity, it is a candidate; if the complexity reappears across callers, the abstraction may be earning its keep.

Treat these as review questions, not automatic refactoring rules. Preserve documented decisions unless concrete current friction justifies reopening them.

## Bounded report

Write a Markdown report outside application code (or return it directly) with this shape:

```markdown
# Architecture Health Review — <date>

- target repository: <owner/repository or local identity>
- exact revision: `<full commit SHA>`
- reviewed scope: <paths, question, and exclusions>
- evidence gathered: <commands, documents, tests, and history consulted>

## Observations

### AH-001 — <short evidence-backed title>

- category: <depth | locality | coupling | boundary leakage | seam | repeated abstraction>
- locations: `<path>:<symbol-or-line>`
- observation: <what the current structure demonstrates>
- evidence: <callers, tests, history, or documented decision>
- confidence: <high | medium | low>

## Uncertainty and counter-evidence

- <what was not inspected, competing explanation, or healthy control>

## Advisory improvements

- <candidate only; expected leverage/locality and why it survives the deletion test>

## Optional alternative designs

- trigger: <explicit high-consequence trigger, or not requested>
- options and criteria: <only when triggered>

## Promotion boundary

No code, Issue, Backlog item, or managed task was created by this review. A human may promote an accepted candidate through the repository's normal Discuss/Backlog/OpenSpec task-intake lifecycle.
```

Observations, evidence, uncertainty, and advisory improvements are separate sections. Include at least one healthy control or counter-example when a heuristic could otherwise over-report a smell. Do not manufacture a finding when the evidence is insufficient.

## Selective alternative-design analysis

Run this mode only when a human explicitly marks a high-consequence trigger, such as a public compatibility interface, cross-subsystem ownership boundary, durable data contract, or costly-to-reverse operational integration. State the trigger and compare at least two materially distinct options against stated criteria: interface knowledge required, locality, compatibility, verification strategy, operational risk, and reversal cost. The comparison is evidence for the current OpenSpec or human decision; it is not a competing specification and does not choose or implement an option automatically.

## Safety boundary

Do not modify repository files, create commits, create or edit Issues, create a Backlog item or managed task, dispatch an agent, publish a report, or start a refactor. State the normal human-promotion path instead. This capability is a review protocol, not an architecture score, a task router, or an autonomous remediation tool.
