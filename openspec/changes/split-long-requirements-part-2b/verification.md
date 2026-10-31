OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (meaning preservation of every split, completeness, coherence) of the 5 spec deltas against the main specs; a mechanical split check per spec; `openspec validate <change> --strict` on 1.13.2 and on an isolated 1.15.0; an archive simulation on a copy of `openspec/` followed by `validate <spec> --type spec --strict` on 1.15.0; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Procedure of DEC-0007 (OpenSpec 1.15.0 specs instruction, Fission-AI/OpenSpec#2020): 32 long requirements in 5 specs became 32 MODIFIED (header and every scenario kept byte-for-byte, description cut to one behavior) and 83 ADDED requirements, each with its own scenario.
- Wording is reused verbatim. Edits beyond splitting: pronouns and demonstratives replaced by the noun phrase they referred to in the same requirement; inherited conditions repeated so each ADDED requirement stands alone (for example "For `harness_mode=platform` and `publish_mode=pr`, …", "For the explicit worktree cleanup operation that removes an abandoned candidate's exact task worktree, …"); "resolve the base by the same rule" now names the rule copied from the MODIFIED sentence.
- Normative form: platform-rollout's descriptive "A conflict is safe when either (a) …, (b) … or (c) …" (no SHALL, an ADDED requirement needs one) became three ADDED requirements "… a conflict SHALL count as safe when (a|b|c) …"; each condition is sufficient on its own, as in the original. MAY/SHOULD-only and descriptive sentences stay with the SHALL behavior they qualify. Ambiguous scope ("Every ordinary merge, auto-merge, or queue-enrollment request …") is kept verbatim without an added prefix.
- This is part B of portion 2 (the package of all 14 portion-2 specs exceeds the GitHub comment size limit).

## Completeness

- Mechanical check (per spec): every long main requirement is covered; MODIFIED scenarios equal the main spec's byte-for-byte; every description ≤ 500; every ADDED has a scenario, SHALL/MUST and a new name; every word of each original description reappears in its split except the replaced pronouns/demonstratives and "either" noted above.
- `openspec validate split-long-requirements-part-2b --strict`: valid on 1.13.2 and 1.15.0; after a simulated archive the 5 specs pass `validate --strict` on 1.15.0.

## Not verified / limits

- The OpenSpec pin stays 1.13.2; portion 3 (5 specs and the bump) remains, 93 long requirements.
