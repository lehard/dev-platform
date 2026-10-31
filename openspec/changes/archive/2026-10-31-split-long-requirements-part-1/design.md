## Context

Decision: DEC-0007 (`docs/decisions/0007-openspec-requirement-length.md`). Procedure: the specs instruction of OpenSpec 1.15.0 (Fission-AI/OpenSpec#2020) — in a change made for that purpose, keep the MODIFIED header and every scenario, cut the description to one behavior without changing its meaning, and add each removed behavior as its own ADDED requirement with its own scenarios. The limit is 500 UTF-16 units of the description (text between `### Requirement:` and the first scenario); scenarios are not counted.

## Decisions

- **Verbatim sentences.** Split at sentence (or clause) boundaries and reuse the original wording; edit only what a sentence needs to stand alone (repeat a subject, resolve a pronoun). No obligation, condition, literal or name is added, dropped, weakened or strengthened.
- **New scenarios restate only their requirement.** An ADDED requirement needs at least one scenario; its scenario states exactly that behavior. The original scenarios stay with the MODIFIED requirement unchanged (the 1.15.0 validator rejects a MODIFIED that omits one).
- **Mechanical guard.** Each delta is checked by a script that requires: every long requirement of the spec is covered, MODIFIED scenarios equal the main spec byte-for-byte, every description ≤ 500, every ADDED has a scenario and SHALL/MUST, and every word of the original description reappears in the split. `openspec validate <change> --strict` passes on 1.13.2 and 1.15.0, and after archive the 18 specs pass `validate --strict` on 1.15.0.
- **Portions.** Portion 1 takes the specs no in-flight change touches plus model-routing; chat-coordinator, publication-queue and platform-lifecycle, which have in-flight changes, go to the last portion together with the version bump.

## Risks

- A later change that MODIFIES one of these requirements from an older long text would reintroduce it; the 1.15.0 bump (portion 3) makes `--strict` catch that.
