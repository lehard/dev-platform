# Systematic bug diagnosis

Use this capability only to diagnose an **unknown** defect, regression, intermittent failure, unexplained degraded performance, or other failure whose cause is not already directly established. It is a reusable evidence-first path, not a replacement task lifecycle or a requirement for every correction.

Do not use the full protocol for an obvious bounded correction: for example, a confirmed local typo, an already-identified one-line configuration value, or a mechanical change whose cause and expected result are directly known. If a seemingly quick correction becomes an unexplained failure or expands materially, stop treating it as a quick task and use this protocol (and the normal task-intake boundary) instead.

## 1. Confirm the failure condition

Before claiming a root cause, establish a runnable reproducer or other direct observable evidence for the reported symptom. Prefer a narrow test; otherwise use a minimal command, request replay, trace, measurement harness, or redacted captured artifact. Record only this bounded evidence:

- **Failure condition:** invocation or artifact identity, relevant input/environment assumptions, expected result, observed result, and whether it is deterministic or its measured reproduction rate.
- **Evidence result:** the observed failure signal, redacted as necessary; do not retain secrets, raw sensitive payloads, or private reasoning.

The condition must exercise the reported symptom, not merely show that nearby code runs. Tighten and minimise it where practical. For a non-deterministic failure, make the trigger repeatable enough to test and state the observed rate.

If direct evidence cannot be obtained, record what was attempted and report the diagnosis as **unconfirmed**. Do not present a plausible story as a proven root cause. Request the missing safe access, redacted artifact, or approval for temporary instrumentation when appropriate.

## 2. Test falsifiable explanations

Before the final production fix, state a small ranked set of competing explanations. For each probe, record only:

| Field | Required content |
| --- | --- |
| Hypothesis | A concise possible cause. |
| Prediction | What observable result would distinguish it. |
| Probe | The bounded experiment or instrumentation used. |
| Result | The relevant observed result and whether it supports or rejects the hypothesis. |

Change one relevant variable at a time. Prefer a debugger/REPL observation or targeted instrumentation at a discriminating boundary over broad logging. Tag any temporary instrumentation with a unique, searchable marker; never expose secrets in its output. A rejected false hypothesis is useful evidence, not wasted work.

## 3. Repair with regression evidence where feasible

When a reasonable automated seam exercises the real bug pattern, write or adapt a regression check before applying the repair. It must fail against the original defect and pass after the repair. Record its path/command and the before/after result.

If no reasonable seam exists because the test would be disproportionate or would miss the real pattern, record that limitation explicitly. Do not fabricate regression evidence or add invalid test coupling merely to satisfy the protocol.

## 4. Close the loop

After the repair:

1. Re-run the original failure condition, not only the new regression check.
2. Run the relevant focused and task-required checks.
3. Remove temporary instrumentation and throwaway debug artifacts; verify the unique marker is absent.
4. Put the bounded diagnosis evidence in the normal task/OpenSpec verification record or PR summary. It informs existing verification and does not create a parallel bug tracker or hidden-reasoning log.

The final report may state the evidence-backed root cause only after the failure condition and discriminating probe support it. Otherwise state the diagnosis is unconfirmed and what evidence would resolve it.

## Representative evidence shape

For an unknown response regression, a useful record is: the request replay returns `500` where `200` is expected; the first probe rejects a suspected timeout because the handler is never entered; a second probe shows a missing parsed field; the focused regression fails before the parser repair and passes after it; then the original replay returns `200` and the temporary marker no longer appears. This is an example of bounded observable evidence, not a request to retain a reasoning transcript.
