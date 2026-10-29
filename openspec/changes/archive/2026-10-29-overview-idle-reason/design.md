## Context

`assess_candidate` already derives the offered job (`build_job`), the winning claim, findings and `expected_automation`. Whether a job kind runs on hosted workers is fixed by `hosted_workers.UNHOSTED`/`HOSTED_KINDS`; attempt limits are `pr_review_gate.MAX_ROUNDS` and `publication_queue.MAX_INTEGRATION_REPAIRS`.

## Decisions

- **A separate `idle` object, not a rewrite of `expected_automation`.** Existing consumers and tests keep their field; `idle` is additive.
- **Idle means open PR with no winning claim.** A merged candidate is outside the requirement. An executing claim yields `null`.
- **Ordered rules, first match wins**, each citing the field it used: no trusted record -> developer; attempt limit reached -> human; blocked-escalation -> human; job present (unclaimed, expired or published) -> worker class from the hosted table (local macOS operator node for `UNHOSTED` kinds, otherwise a lifecycle worker); integration states and retry -> publication queue; `contribution-integrated` -> Requirement composition; else `unknown`.
- **Truthfulness.** A reason is emitted only when its rule's inputs are present; the macOS claim is made only for kinds in `UNHOSTED` whose class table states a local operator node. Unmatched state is `unknown`, never a guess.
- Wording is English like the rest of the script; the unknown case reads "idle reason unknown".

## Risks

- A new state added to `candidate_lifecycle.STATES` falls into `unknown` until a rule is added; a test asserts every state is classified or explicitly unknown.
