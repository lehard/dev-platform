## Context

The owner's decision is recorded in BR-781 (variant A of three, 2026-10-23). The three surfaces already exist: friction root issues (with merge-roots), `docs/decisions/` (decision-registry spec) and OpenSpec proposals.

## Decisions

- Rules live in the central platform docs that agents already read at the matching concern; downstream template docs are not changed, because generated projects have no decision registry. The shared `requirement-authoring` capability gets a repository-neutral wording of rule 1 (link the root issue and list earlier attempts in `Context`).
- DEC-0004 is the main-advance revalidation record; DEC-0005 and DEC-0006 already exist, and the number 0004 was reserved for this record.
- Public text names Requirements by their public `BR-N` identity and public PR numbers only (DEC-0002), never private Backlog Issue links.

## Risks

- The rules are guidance enforced by review, not by a gate; no new check is added.
