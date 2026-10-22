## Context
Spike probes (`probes.sh`, `probes-git.sh`, `writer-claude.sh`, machine-local) used hand-edited paths and a manual token export. The sandboxed Claude dispatch and the sandboxed writer launch primitive now provide the platform launch, profile and scoped token.

## Decisions
- The probe command builds its synthetic integration repository, linked worktree and bare remote under a fresh temporary directory, and treats them as the protected paths of the generated profile.
- The writer receives one fixed probe prompt; the harness never trusts the writer's own report and re-checks integration file tree, all refs (`git for-each-ref`) of the integration repository and of the bare remote before and after.
- The report records each probe as refused or succeeded from harness-side evidence where available (refs, files, remote) and from the writer transcript only for read probes; any success or change exits non-zero.
- DEC-0003 records the sandboxed writer decision only; CI-only merge authority is referenced as BR-575's independent boundary.

- The synthetic repositories live under `repos/` and the disposable checkout under `sandbox/` of the work directory, because the disposable sandbox root may not contain its source repository.
- Reads are judged from the writer's reported exit codes (the only evidence for a refused read), writes and ref/remote moves from harness-side snapshots, and a token leak from writer stdout/stderr.

## Risks
A real run costs a small model budget and needs the operator token file; without it the command refuses explicitly.
