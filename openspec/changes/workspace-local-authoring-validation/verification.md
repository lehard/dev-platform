OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review of proposal, delta, design, implementation and regression evidence
Automated-Checks-Evidence: automated-checks.json

## Semantic review

Completeness: both added managed-task-intake requirements are implemented. Placement uses the integration configuration and reviewed platform worktree storage; exact detached prepared SHA is retained. Cleanup and interruption recovery use one helper receipt and the existing cleanup entrypoint, with explicit errors and exact identity checks.

Correctness: real Git with the actual local_workspace checkout policy reproduces the system-temp rejection observed in public process issues #302 and #316 and admits the repaired helper placement. Existing stale-source exact-state regressions continue to prove the prepared revision is observed without changing source HEAD/content. Hook rejection, validation exceptions, KeyboardInterrupt and killed-owner recovery exercise actual registrations. Recovery refuses live owners, symlinks, changed SHA, foreign contents and active/unobservable cwd state. No policy hooks or admission checks were disabled.

Coherence: proposal, design, delta, runtime, cleanup entrypoint and local-workspace documentation agree. Configuration has one required placement strategy, with no alternate temp directory. Rendering and normal reviewed Copier updates deliver the shared template runtime to new and existing projects. Publication remains the configured coordinator lifecycle; this receipt does not claim terminal merge.

## Evidence and limits

- Real authored package validation on the reviewed host passed with its unchanged ordinary system TMPDIR outside reviewed roots. This exercised the helper with real Git hooks and unmodified shared permission checks.
- materialize-handoff without override passed and reused the existing child; this idempotent re-entry is separate from the actual helper validation above.
- Exact-state regression suite: 32 tests passed. Workspace/cleanup/shared-permission regression invocation: 144 tests passed before the final strict cwd adjustment; the adjusted strict observer and actual SIGKILL recovery subsequently passed their two focused tests.
- compileall, ruff, managed-project registry validation, lifecycle hygiene and strict OpenSpec structural validation passed.
- Real-Git unit fixtures explicitly isolate directory setgid expectations, independent of host support; the Mac system-temp volume cannot retain that bit. Separate shared-permission tests and actual reviewed-host validation retain the real enforcement. Their Git admission policy remains real. Foreign uid rejection uses a simulated lstat uid; active/unavailable cwd refusal uses explicit injected observations. Killed-owner recovery and the host cwd observation use real lsof.
- A hard interruption before receipt publication or with an unverifiable marker requires explicit owner investigation; recovery refuses that ambiguous state. Cleanup does not prune or delete sibling worktrees.
- Full canonical suite passed: 1973 tests across 17 groups, no failed groups. The final explicit unit-fixture version subsequently passed all 32 exact-state tests again. A concurrent selector run failed in harness_replay because candidate commits moved source HEAD during its isolation check. This is execution interference: the separate full run passed, and the replay correctly rejected the moving source. The selector rerun with source HEAD held stable passed affected precheck, compileall, ruff and the complete canonical suite. Its successful content-bound receipt is automated-checks.json.
