# Design: Evidence-first diagnosis without hidden reasoning capture

## Decisions

1. **Capability mechanics come from #87.** This change owns diagnosis behavior only; it must not define another registry, project opt-in schema, provider-materialization path, provenance store or update/remove lifecycle.
2. **Trigger on diagnosis, not every edit.** Unknown bugs, regressions and unexplained failures use the protocol; obvious local corrections can remain quick work.
3. **Observable evidence only.** Persist reproducer conditions, hypotheses/results and checks in bounded form; never require chain-of-thought storage.
4. **Reproducer before root cause.** If the failure is not reproducible or otherwise directly evidenced, the cause remains unconfirmed.
5. **Falsifiable hypotheses.** Agents test competing explanations with bounded instrumentation/experiments rather than editing code on the first plausible story.
6. **Regression before fix where possible.** A useful test should fail for the original defect and pass after repair; lack of a reasonable seam is recorded explicitly.
7. **Close the loop.** Re-run the original failure path and relevant checks after the fix, then remove temporary instrumentation.
8. **Existing lifecycle remains authoritative.** Diagnosis evidence informs the task/OpenSpec verification; it does not create another bug state machine.
