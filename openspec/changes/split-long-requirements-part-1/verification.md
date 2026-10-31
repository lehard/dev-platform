OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (meaning preservation of every split, completeness, coherence) of the 18 spec deltas against the main specs; a mechanical split check per spec; `openspec validate <change> --strict` on 1.13.2 and on an isolated 1.15.0; an archive simulation on a copy of `openspec/` followed by `validate <spec> --type spec --strict` on 1.15.0; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Split procedure from the OpenSpec 1.15.0 specs instruction (Fission-AI/OpenSpec#2020): every requirement with a description over 500 UTF-16 units is MODIFIED under its header with all scenarios kept and its description cut to one behavior; each removed behavior is ADDED with its own scenario. 57 long requirements in 18 specs became 57 MODIFIED and 181 ADDED requirements.
- Wording is reused verbatim. Edits beyond splitting: a pronoun or demonstrative replaced by its noun, a subject or condition repeated so a sentence stands alone, and a few connectives dropped ("More broadly", "Instead", "such"). Single sentences over 500 were split at clause boundaries; in model-routing "Verified concurrent integration advancement is distinct from a delegated escape" the condition list moved into the ADDED "Qualifying conditions for a verified concurrent integration advance", referenced from the MODIFIED text. In local-platform-hotfix the divergence-check condition list was regrouped into three sentences with the same subject.
- DEC-0007 records the owner decision (upstream path; B, C and D rejected).

## Completeness

- Mechanical check (per spec): each long main requirement is covered; MODIFIED scenarios equal the main spec's byte-for-byte; every description ≤ 500; every ADDED has a scenario and SHALL/MUST and a new name; every word of each original description reappears in its split (remaining differences: punctuation-adjacent tokens and the replaced pronouns/connectives listed above).
- `openspec validate split-long-requirements-part-1 --strict`: valid on 1.13.2 and 1.15.0. After a simulated archive all 18 specs pass `validate --strict` on 1.15.0.
- Existing fallback wording in goal-definition ("MAY fall back to an equivalent transient natural-language goal refinement") is kept verbatim: this change is form-only.

## Not verified / limits

- The OpenSpec pin stays 1.13.2; `validate --all --strict` on 1.15.0 still fails on the 19 specs of portions 2 and 3.
- A later change that MODIFIES one of these requirements from its old long text would reintroduce it; the 1.15.0 bump catches that under `--strict`.
- Independent review: ready; one advisory (blocking-check-recovery ADDED sentences lost their antecedent) fixed by naming the failure-class catalog and the `preflight`/`no_preflight` fields explicitly. "The Requirement" is kept verbatim from the original text.
