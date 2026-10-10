## 1. Classification

- [ ] 1.1 In `template/scripts/publication_state.py::_observe_required_checks`, return `pending` with one `EXPECTED` row per required context when gh reports no required checks on a main-targeted PR whose base requires contexts. Keep `not_registered` when the base requires none. Mark the contribution path's missing rows and missing App-bound runs as `EXPECTED`.

## 2. Bounded queue wait

- [ ] 2.1 In `template/scripts/publication_queue.py::_integrate`, when `CHECK_WAIT_SECONDS` expires on a pending observation whose rows are all `EXPECTED`, block the candidate with a reason that names the unreported checks and the bound. Other pending observations keep the `waiting` result.

## 3. Tests

- [ ] 3.1 `tests/test_publication_state.py`: replace `test_no_required_checks_while_base_requires_some_is_malformed` with a pending/EXPECTED assertion that names the context. Cover the contribution `EXPECTED` rows. Keep the transport, malformed and head-mismatch tests.
- [ ] 3.2 `tests/test_publication_queue.py`: the race (first observation unreported, then passed) integrates. An observation that stays unreported past the bound blocks with the named reason. A reported-pending observation past the bound stays `waiting`.

## 4. Readiness

- [ ] 4.1 Real dogfood: the queue integrates at least one candidate after merging `main` into it with this change on `main`. Record the PR, the head and the queue run in `verification.md`.

## 5. Delivery

- [ ] 5.1 Required platform checks, truthful verification, archive, retrospectives, publication.
