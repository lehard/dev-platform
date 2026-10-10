OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the delegated implementation diff against the publication-queue delta, proposal, design and tasks; local independent review (spec-fidelity, engineering-quality) on the final content; repository-owned selected checks on the reconciled head
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Implementation: a delegated native Claude executor implemented tasks 1.1, 2.1, 3.1 and 3.2; its execution was recorded with record-claude-execution and a clean containment postcheck. The supervisor reviewed the diff and aligned design.md with one addition the executor made beyond it (the bounded block first calls `_raise_if_owned_elsewhere`, as the existing not_registered block path does, so it never overwrites a review or repair claim taken while checks ran).

Completeness: `publication_state._observe_required_checks` returns pending with one `EXPECTED` row per required context when gh reports no required checks on a main-targeted PR whose base requires contexts (not_registered is kept when the base requires none); the contribution path marks missing rows and missing App-bound runs as `EXPECTED`. `publication_queue._integrate` blocks with a reason naming the unreported checks and the bound when `CHECK_WAIT_SECONDS` expires on an all-`EXPECTED` observation; other pending observations keep the waiting result. Tests: tests/test_publication_state.py (test_no_required_checks_while_base_requires_some_is_pending_expected, contribution EXPECTED rows, App-binding EXPECTED row) and tests/test_publication_queue.py (unreported-then-passed integrates, unreported past the bound blocks naming the checks, reported pending past the bound still waits).

Correctness: transport, malformed payload, head-mismatch and unsupported-state classifications are unchanged; pending never authorizes publication in any consumer (project_publish waits within its bound, rollout_preflight reports PENDING_CHECKS, finish keeps the armed PR resumable). No candidate is integrated without passed required checks.

Coherence: the delta replaces the spec clause that called this condition unusable with a pending scenario and a bounded-expiry scenario; code and tests match it.

Independent review (final content): spec-fidelity and engineering-quality, no findings (run three times: initial package, after the design/tasks alignment, and on the reconciled package with tasks complete).

Readiness: the publication-queue workflow runs only protected-main code, so the real-integration observation is recorded in the Requirement retrospective after merge (design.md, Readiness).

Checks actually run: `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/queue-unreported-checks-wait/automated-checks.json` on the reconciled head (contains origin/main 1b032a6), after the final independent review: affected precheck success, compileall success, ruff success, `run_test_groups.py --all` success (489 s).
