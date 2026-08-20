# Design: deterministic pre-entrypoint exact-head migration

## Failure mode

Appending Python definitions after an `if __name__ == "__main__"` block does
not change a direct script invocation: Python reaches the guard and exits
before parsing reaches the appended definitions at runtime.

## Decision

For each reviewed exact SHA-256 legacy source, Dev Platform will insert a
small generated exact-head import/override block immediately before the unique
top-level CLI guard. The migration refuses sources with no unique guard, an
unrecognized fingerprint, or an already partial migration. The generated
helper remains platform-owned rollout output, while all Jara/Planner-specific
functions outside the bounded override remain byte-preserved.

This placement guarantees that function names used by the original `main()`
resolve to the exact-head replacements before `main()` executes. It preserves
Jara's board/worktree/serialized integration orchestration and Planner's
standalone integration-clone orchestration because only their publication
surface functions are rebound.

## Rollout risk and mitigation

The migration touches project-owned harnesses during a cross-repository
release. It therefore accepts only an exact reviewed legacy SHA-256 or the
known `v1.4.34` append form whose removed suffix reconstructs that exact
source. It verifies the unique guard and complete helper before writing either
file. Any unknown source, guard shape, or partial helper state blocks with no
downstream write. The standard release rollout creates a reviewed replacement
PR and closes an older bot-owned rollout only after the replacement exists;
it never auto-merges a downstream PR.

## Verification

- Run synthetic migrated fixtures with `python script.py ...`, not imports.
- Simulate historical merged PR A plus reused branch/current head B and prove
  B cannot reach terminal success or cleanup through A.
- Assert Jara and Planner orchestration sentinels still execute.
- Assert byte drift leaves the source untouched and blocks rollout.
