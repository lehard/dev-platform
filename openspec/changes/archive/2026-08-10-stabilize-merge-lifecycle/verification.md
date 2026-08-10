# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal/design/delta spec plus Platform CI run 31402720855 on implementation head e9780d0032dde1863cd0159118ca29c0a544caec

## Automated validation

Platform CI completed successfully on the implementation head. It passed:

- shared-script compilation;
- managed-project registry validation;
- the full unit suite, including the new merge-lifecycle resilience tests;
- OpenSpec lifecycle hygiene;
- strict OpenSpec validation;
- template rendering;
- Copier upgrade-path smoke tests;
- mature project-harness adoption smoke tests;
- project-harness smart-update fallback smoke tests.

## Semantic review

Completeness: PASS. The implementation covers each in-scope incident class from the proposal: stale token fallback, delayed required-check registration, protected merge-policy fallback, authoritative merged-state handling, and rerun recovery after a remote squash merge.

Correctness: PASS. GitHub remains authoritative for protected integration. Required checks are not bypassed, waits are bounded, local main moves only after a confirmed remote merge, merge fallbacks do not use administrative bypass, and exact PR head matching prevents an unrelated merged PR from being treated as recovery for a changed local branch.

Coherence: PASS. The code, design, and delta specification agree on credential precedence, bounded check registration, merge-mode negotiation, post-merge cleanup semantics, and idempotent reconciliation. Existing platform-owned lifecycle tests remain green.

## Known follow-up boundary

Jara_Fin uses `harness_mode=project`, so its repository-owned `merge_to_main.py` is intentionally not replaced by this platform implementation. It must be aligned separately after the platform release. Delegated-agent filesystem containment is also outside this change because enforcement spans external Claude/Codex runtime behavior rather than only the repository Git lifecycle.
