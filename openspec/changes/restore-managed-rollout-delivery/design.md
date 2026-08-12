## Context

The rollout subsystem already has the correct high-level safety model: immutable SemVer input, structured failure diagnostics, fail-closed Copier handling, reviewed downstream PRs and durable per-project failure streaks. The current incident should therefore be repaired inside that model rather than by adding another rollout path.

## Decisions

### Diagnose per repository before changing shared code

Use the existing canonical diagnostic artifact/summary first, then only the narrow workflow/job evidence needed to explain the recorded stage. Cuby already has a concrete Copier-conflict signal; Jara_Fin and planner-agent-lab need the narrow `unknown` stage resolved before deciding whether they share code changes.

The v1.4.26 evidence establishes two independent platform-owned defects. Cuby's
platform-harness workflow is unchanged from its rendered v1.4.24 baseline, but
the guarded-recopy proof compared that rendered file with raw Jinja source. The
proof must render the recorded immutable baseline (and the target for the
post-recopy assertion) with the downstream's recorded Copier answers in an
isolated, task-free directory. Jara_Fin and planner-agent-lab reached the final
cached-diff whitespace guard, whose `SystemExit` escaped the `ValueError`
blocker boundary and therefore produced `unknown`; command failures must remain
fail-closed while being emitted as structured blockers.

The v1.4.27 retry found one residual Cuby-only formatting drift: its committed
platform-owned `dev-platform.yml` removes one redundant blank separator from the
v1.4.24 rendering.  Baseline equivalence may collapse repeated blank separators
only for that generated workflow, and only while it has no YAML block scalar
where blank lines are content.  Comments, non-empty lines, all other paths, and
block-scalar workflows stay byte-sensitive.  The post-recopy target comparison
remains exact bytes, so the recovery writes the candidate rendering rather than
preserving formatting drift.

The same retry then demonstrated that application validation can create
disposable build outputs in the isolated downstream checkout.  The rollout
commit must capture the reviewed Copier/bootstrap result before checks execute;
otherwise a blanket post-check `git add -A` can accidentally deliver generated
files or fail on their whitespace.  Check failures remain blockers, but their
filesystem side effects are intentionally outside the staged reviewable diff.

### Keep permission ownership with backlog #12

`enforce-shared-workspace-permissions` owns cross-user filesystem/Git permission semantics. This change may identify that a rollout failed because of those semantics, but must not fork their implementation. Such a leg becomes an acceptance dependency; other rollout causes remain independently actionable.

### Validate recovery on the current cumulative release

If #12 or another repair produces a newer immutable release before acceptance, use that current cumulative release rather than forcing historical v1.4.25 deployment. The acceptance target is restored delivery health across all managed inventory, while evidence retains the v1.4.25 incident roots.

## Risks / Trade-offs

- Treating all three failures as one bug could hide project-specific conflicts; diagnose separately.
- Auto-resolving Copier ownership conflicts would trade reliability for silent drift; remain fail-closed.
- Waiting for #12 globally would unnecessarily serialize unrelated rollout repairs; dependency is per confirmed root cause only.
