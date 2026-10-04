# Full-suite timing decision

Host: operator Mac, same worktree, `python3 scripts/run_test_groups.py --all`, auto-capped `jobs=4`.
Coverage parity: `--verify-coverage` reported identical discovered/declared sets before and after
(1660 tests before; 1668 after only because this change adds 8 guard/precheck tests); no test removed.

| Run | Layout | Wall clock | Slowest group | Group seconds total | Outcome |
| --- | --- | --- | --- | --- | --- |
| 1 (before) | 15 groups, `fast-b` 642 tests declared late | 11m28.7s | fast-b 496.4s | 1752.6 | success |
| 2 (after) | 17 groups, fast-b split into fast-b/e/f, heavy groups declared first | 10m51.5s | 417.5s | 2426.6 | fast-c failed (startup-timing test) |
| 3 (after) | same | 9m49.5s | fast-c 364.8s | 2224.2 | fast-c failed (startup-timing test) |
| 4 (after, timing fix) | same | 9m38.8s | 451.2s | 2200.5 | success |

Per-module isolation timing of the old fast-b located the cost in `test_independent_review`
(~239s) and `test_requirement_integration` (~192s); the split places them in different groups
(fast-b ~258s, fast-e ~254s, fast-f ~211s in run 3).

Decision: adopt the split plus heavy-first declaration order. Wall clock fell in every
comparable after-run (−5% to −16%); group seconds rose because more heavy groups contend at
once, which surfaced a fragile 10s readiness window in
`test_pr_reconciliation_concurrency` (helper imports the full finish_task chain). That
helper now waits on the shared bounded process deadline (30s, overridable), which still
fails a genuinely hung helper. Remaining serial boundary: the 4-job cap; no change made to it.
