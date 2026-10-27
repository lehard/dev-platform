## Why

BR-767 was delivered by three quick PRs and has no managed children. `requirement_retrospective.py checkpoint` refused it ("needs an unambiguous, nonempty child set"), so the retrospective was written by hand as an Issue comment (friction ab37fd25399a). Several open Requirements are partly delivered by quick PRs and cannot be closed through the standard path.

## What Changes

- `checkpoint` takes `--quick-pr owner/repo#N` (repeatable). Each named PR must be merged; otherwise the checkpoint stops naming it.
- An empty `requirement-children` block is accepted only together with at least one `--quick-pr`; without one the refusal names the option. Duplicate children still stop.
- The receipt records `quick_prs`; `require_checkpoint` accepts an empty child set only when the receipt names quick PRs, and otherwise keeps every existing check.
- Requirements with managed children behave as before; `--quick-pr` may also be given for a Requirement delivered partly by quick PRs.

## Impact

`template/scripts/requirement_retrospective.py`, `tests/test_requirement_retrospective.py`, generated platform manifest. Spec `agent-workflow`: one added requirement.
