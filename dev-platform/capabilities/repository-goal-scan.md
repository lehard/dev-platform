# Repository goal scan

Use this capability only when a human explicitly requests a broad,
whole-repository investigation for an engineering goal: for example, “scan the
repository for every use of a deprecated boundary” or “find reliability risks
across this codebase.” It is advisory evidence, not implementation, review
ceremony for a local change, or a second task system.

Do not introduce it for a scoped implementation, bug fix, focused review, test
run, or ordinary debugging request. Findings never create source changes,
Issues, managed tasks, PRs, project status, or Backlog entries. A human promotes
an accepted finding through the usual quick-task or managed OpenSpec lifecycle.

The descriptor is `explicit-only`. Current provider surfaces report that native
invocation-control limitation rather than pretending an automatic skill router
can enforce it; invoke this documented protocol explicitly when the capability
is enabled.

## Plan → deterministic Shard → Map → Reduce

1. **Plan.** State the engineering goal, a bounded question/acceptance signal,
   supported selectors, include/exclude scope, known blind spots, and a positive
   batch bound. The v1 selectors are `inventory`, `fixed`, and `regex`; they do
   not execute planner-authored shell code, downloaded code, AST queries, or
   call-graph programs. Use a conservative supported selector when recall is
   important, and record semantic limitations explicitly.
2. **Shard.** Run `python3 scripts/repository_goal_scan.py plan --profile
   <profile.json> --out .dev-platform/repository-goal-scan/<run>` (optionally
   `--revision <ref>`). The adapter resolves a full commit SHA and reads its
   tracked Git tree, so ambient uncommitted files do not affect the run. Inspect
   the finite manifest before Map work begins.
3. **Map.** Process every assigned candidate in each batch. Native read-only
   delegation may process independent batches, or the active executor may work
   sequentially. This capability does not create provider sessions, a scheduler,
   branches, worktrees, or a task lifecycle. Record exactly one `finding` or
   `no-finding` verdict for every candidate with `record`; an omitted, duplicate,
   extra, pending, or failed candidate/batch is not coverage.
4. **Reduce.** Synthesize the structured verdicts and cited source locations.
   Preserve candidate and batch IDs, confidence, impact rationale, and material
   counter-evidence. Inspect cited surrounding code only when needed to
   reconcile/deduplicate; do not silently restart an unbounded repository search.

Run `status` to read accounting and `finalize` to write a coverage receipt. A
complete receipt means **100% selected-scope processing**, not proof that every
relevant repository issue was selected. Keep selector limitations, exclusions,
and selection confidence visible even after all batches are valid.

## Evidence boundary

The default `.dev-platform/repository-goal-scan/` state is machine-local. Keep
only the profile, manifest, structured verdicts, bounded findings, and coverage
receipt. Do not put raw prompts, provider transcripts, chain-of-thought,
credentials, or unrelated source copies into scan evidence.

This is an independent adaptation of Cognition's published Agentic MapReduce
architecture: deterministic finite selection and accounting around reasoning.
It vendors no Cognition content or runtime and is not dependent on Cognition.
