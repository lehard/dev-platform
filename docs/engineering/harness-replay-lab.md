# Harness Replay Lab

`scripts/harness_replay.py` is a small, advisory evaluation surface for Dev
Platform harness/process candidates. It is not an executor, benchmark farm,
router, release gate, or self-improvement loop.

A frozen suite has 5–10 cases. Every case pins the exact source revision that
is reconstructed in a disposable detached clone, plus digested canonical
OpenSpec contract and independent verification/check evidence. Run:

```bash
python3 scripts/harness_replay.py --suite dev-platform/harness-replay/cases.json validate
python3 scripts/harness_replay.py --suite dev-platform/harness-replay/cases.json evaluate \
  --candidate candidate.json --report replay-report.json
```

Candidate evidence must bind to the suite digest and explicitly declare the
required `verification=pass` and `reference=match` capability gate. A failed
case receives no efficiency comparison or positive savings conclusion. For
qualified cases, payload, usage, time, cost, retries, escalations and human
interventions remain `unknown` unless both baseline and candidate provide a
semantically comparable value. Deterministic payload changes are not token
savings.

The included native control reuses each pinned historical successful checks
receipt. Its check wall time compares at delta zero; token, cache and cost
remain unknown. The controlled failure fixture demonstrates gate ordering with
simulated candidate outcomes. It is not evidence that a real shorter prompt
passed or failed on a historical task. External candidate observations need
their own independent verification before a managed optimization decision.

Each candidate labels one or more supported harness changes: shorter
instructions, lazy capability definitions, reduced delegation guidance, or
cache-friendly prompt/tool boundaries. Each label goes through the same gate;
an upstream resource claim is not local replay evidence.

The runner does not execute candidate commands. It only materializes the exact
case revision in a temporary clone and evaluates bounded evidence produced by a
separate candidate runner. This prevents candidate data from mutating the
integration checkout or becoming its own ground truth. Reports are advisory:
they never modify routing, context policy, runtime defaults, release state or
the Development Backlog. Any resulting policy change requires a separate
managed change.
