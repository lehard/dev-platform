# Design: safe validation-feedback optimization

## Baseline and observability first

The implementation will measure elapsed wall-clock duration, selected check set, and result for every validation command. Normal successful output will be concise; on failure the runner will retain and emit the command, exit status, and bounded relevant output tail or artifact location. Baseline and comparison runs will distinguish isolated and contended local execution so a resource-contention symptom is not misrepresented as test-suite cost.

## Two explicitly different policies

`local affected` is a developer-feedback policy. It may run a proof-backed subset only when every changed path maps to a maintained, tested selector rule. `protected full` is the merge-authority policy and always includes the complete required platform validation set. A local selected success is informational and cannot satisfy, replace, or rename the protected full required check.

The selector treats unknown paths, selector/configuration changes, workflow files, OpenSpec changes, lifecycle code, and any ambiguous classification as full-suite triggers. The change will enumerate the final trigger map in code and tests rather than deriving authority from naming conventions.

## Partitioning only after isolation audit

Before parallel execution, inventory each candidate check's mutable resources: temporary directories, databases, artifact paths, locks, ports, external state, and interpreter/process-global configuration. A partition is eligible only when its resources are demonstrably isolated per worker or it is serialized. The CI workflow retains a stable aggregate check name that reports failure if any selected mandatory partition fails. Full-suite dispatch remains available for scheduled/manual verification.

## Rollout and acceptance

1. Capture baseline duration distributions and identify output/coordination overhead.
2. Land timing and quiet diagnostics with regression tests.
3. Add policy-aware selection and prove the protected full gate independently from local selection.
4. Benchmark candidate partitions under isolated and contended conditions; introduce only partitions that preserve determinism and resource isolation.
5. Compare p50/p95 elapsed time and failure-diagnosis quality against baseline; document trade-offs and retain a full fallback.

No cached receipt, prior local success, or heuristic similarity may replace an actual required protected PR validation run.
