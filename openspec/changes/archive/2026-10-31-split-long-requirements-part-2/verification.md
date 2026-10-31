OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (meaning preservation of every split, completeness, coherence) of the 9 spec deltas against the main specs; a mechanical split check per spec; `openspec validate <change> --strict` on 1.13.2 and on an isolated 1.15.0; an archive simulation on a copy of `openspec/` followed by `validate <spec> --type spec --strict` on 1.15.0; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Procedure of DEC-0007 (OpenSpec 1.15.0 specs instruction, Fission-AI/OpenSpec#2020): 49 long requirements in 9 specs became 49 MODIFIED (header and every scenario kept byte-for-byte, description cut to one behavior) and 136 ADDED requirements, each with its own scenario.
- Wording is reused verbatim. Edits beyond splitting: pronouns and demonstratives replaced by the noun phrase they referred to in the same requirement; subjects and conditions repeated so each ADDED requirement stands alone (for example "In a platform test, …", "In the Requirement end-to-end metrics report, …"); sentences over 500 split at a clause boundary (agent-workflow ADD projection content list; ADD state, where "otherwise" became "otherwise, when neither «утверждён» nor a stale or unprovable approval applies"; upstream-substitution's 8-item decision list split after "security and privacy effects").
- Normative form: in managed-task-intake "Execution intent authorizes these steps without a separate fixation request." is stated as a SHALL ADDED requirement naming those steps (an ADDED requirement needs SHALL/MUST); its exception sentence stays in the MODIFIED requirement. MAY/SHOULD-only sentences stay with the SHALL behavior they qualify. An ambiguous "the Requirement" is kept verbatim.
- Portion 2 is published in two parts because the managed package of all 14 specs exceeds the GitHub comment size limit (422); this is part A.

## Completeness

- Mechanical check (per spec): every long main requirement is covered; MODIFIED scenarios equal the main spec's byte-for-byte; every description ≤ 500; every ADDED has a scenario, SHALL/MUST and a new name; every word of each original description reappears in its split except the replaced pronouns/demonstratives and connectives listed above.
- `openspec validate split-long-requirements-part-2 --strict`: valid on 1.13.2 and 1.15.0; after a simulated archive the 9 specs pass `validate --strict` on 1.15.0.

## Not verified / limits

- The OpenSpec pin stays 1.13.2; part B (5 specs) and portion 3 (5 specs and the bump) remain.
- The private Backlog Issue body still lists the original 14 specs; the published managed package (9 specs) is canonical.
