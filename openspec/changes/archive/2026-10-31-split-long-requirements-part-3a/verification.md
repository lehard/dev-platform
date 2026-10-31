OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (meaning preservation of every split, completeness, coherence) of the 2 spec deltas against the main specs; a mechanical split check per spec; `openspec validate <change> --strict` on 1.13.2 and on an isolated 1.15.0; an archive simulation on a copy of `openspec/` followed by `validate <spec> --type spec --strict` on 1.15.0; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Procedure of DEC-0007 (OpenSpec 1.15.0 specs instruction, Fission-AI/OpenSpec#2020): 46 long requirements in completion-lifecycle and platform-lifecycle became 46 MODIFIED (header and every scenario kept byte-for-byte, description cut to one behavior) and 145 ADDED requirements, each with its own scenario.
- Wording is reused verbatim. Edits beyond splitting: pronouns and demonstratives replaced by the noun phrase they referred to in the same requirement; subjects and inherited conditions repeated so each ADDED requirement stands alone (for example "One bounded exception to the fresh task base requirement SHALL exist", "During finalization, …", "For a coordinator-managed candidate, …" where the original sentence sat under that condition); single sentences over 500 split at a clause boundary (the `lifecycle_preflight.py` registry list at its colon; the machine-pool acquisition sentence into ordering/timeout and load-wait requirements). Ambiguous phrases are kept verbatim.
- Handed off with the change active (BR-940); the coordinator's finalize archives.

## Completeness

- Mechanical check (per spec): every long main requirement is covered; MODIFIED scenarios equal the main spec's byte-for-byte; every description ≤ 500; every ADDED has a scenario, SHALL/MUST and a new name; every word of each original description reappears except replaced pronouns/demonstratives and connectives.
- `openspec validate split-long-requirements-part-3a --strict`: valid on 1.13.2 and 1.15.0; after a simulated archive both specs pass `validate --strict` on 1.15.0.

## Not verified / limits

- The OpenSpec pin stays 1.13.2; part B (lifecycle-workers, publication-queue, chat-coordinator, 47 long requirements) carries the 1.15.0 bump.
