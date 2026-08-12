# Cloud pilot evidence

## Scope

This evidence covers the central `dev-platform` GitHub Agentic Workflows cloud
pilot and the completed local friction-routing acceptance. The completion
integration relies on the now-archived `durable-publication-recovery` surface.
No rollout was made to Cuby, Jara_Fin, or Planner Agent Lab.

## 2026-08-11 manual Actions acceptance

The repository Actions secret contract was validated by the successful
activation step `Validate CODEX_API_KEY or OPENAI_API_KEY secret`; the secret
value was not read or logged.

| Workflow | Run | Result | Observed safe output | Audit usage |
| --- | --- | --- | --- | --- |
| Process Issue Triage | [31472738182](https://github.com/lehard/dev-platform/actions/runs/31472738182) | Success, 6/6 jobs | No GitHub write (`noop`); see limitation below | 5.4 min wall time, 86.9k tokens, 7.53 AIC, 18 firewall requests |
| Weekly Process Backlog Review | [31471123098](https://github.com/lehard/dev-platform/actions/runs/31471123098) | Success, 5/5 jobs | Created exactly one allowed report issue: [#98](https://github.com/lehard/dev-platform/issues/98) | 4.6 min wall time, 67.6k tokens, 8.20 AIC, 16 firewall requests |
| Process Issue Triage (post-fix) | [31477078649](https://github.com/lehard/dev-platform/actions/runs/31477078649) | Success, 6/6 jobs | Read #96 body and `process` label; safe outputs added exactly one [triage comment](https://github.com/lehard/dev-platform/issues/96#issuecomment-5251306082) | 4m03s wall time; primary 8.399 AIC (81,874 input / 1,861 output tokens) + detection 0.715 AIC (37,397 input / 1,350 output tokens); 16/16 firewall requests allowed |

The outcome check immediately after the weekly run recorded #98 as `ignored`
because it was still open without engagement. This is an observation-window
result, not a failed safe output.

Two earlier controlled triage runs
([31471123015](https://github.com/lehard/dev-platform/actions/runs/31471123015)
and [31471624719](https://github.com/lehard/dev-platform/actions/runs/31471624719))
also completed successfully with no GitHub write. This confirms that the
fail-safe route has no hidden write path.

## Safety and limits observed

- The agent jobs ran with `contents: read` and `issues: read`; all writes are
  isolated in generated safe-output jobs.
- No implementation pull request, repository code write, merge, approval, or
  source-issue closure was created. A post-run open-PR query returned none.
- Process Issue Triage is capped at 50 AIC/run, 100 AIC/day, 8 minutes, and 8
  turns; its threat detection is capped at 25 AIC.
- Weekly Process Backlog Review is capped at 100 AIC/run, 100 AIC/day, 10
  minutes, and 10 turns; its threat detection is capped at 25 AIC.
- Observed usage was far below the configured per-run caps, so no cap increase
  is justified.

## Gateway blocker diagnosed

`dev-platform` is public; it was not a private-repository prompt or permissions
problem. In run 31472738182, gh-aw correctly detected public visibility and
forced the GitHub read scope to `public`, with `min-integrity: none` and the
configured `issues,labels` toolsets. The generated lock nevertheless started
the gh-aw 0.85.4 default gateway, `gh-aw-mcpg:v0.4.8`. That gateway assigned a
`private` secrecy tag to GitHub MCP responses for this public repository, so it
filtered `issue_read` and `list_label` before Codex could receive them.

Upstream tracked this as the public-repository secrecy-tag regression and fixed
the missing response-visibility path in `gh-aw-mcpg:v0.4.9`. The repository
compiled-lock configuration now maps the default gateway to the immutable
v0.4.9 image and constrains GitHub MCP reads to `allowed-repos: public`; it does
not enable `private-to-public-flows` or widen GitHub repository visibility.

The first post-fix triage run,
[31475984733](https://github.com/lehard/dev-platform/actions/runs/31475984733),
proved the secrecy fix: Codex received #96's body and `process` label through
the GitHub MCP with no DIFC filtering. It did not complete acceptance because
`gh-aw-mcpg:v0.4.9` then rejected the `v0.85.4` compiler's own read-write
workspace mount for the `safeoutputs` backend. This is a separate runtime
compatibility defect introduced by v0.4.9's trusted host-mount policy, not a
prompt, repository-permissions, or private-data-flow failure. The pilot now
uses that policy's documented exact-path allowlist for only the three
compiler-owned safe-output mounts.

The post-fix main-branch run 31477078649 completed the acceptance: GitHub MCP
`issue_read` returned #96's body and label data without `difc_filtered`, and
the `safeoutputs` write-sink accepted one `add_comment` with `secrecy: public`
and applied it to #96. The run registered no code-write or implementation-PR
path. After that proof, temporary fixtures #96, #100 and #101, plus failed-run
reports #99 and #108, were closed. The actual backlog report #98 remains open.

`gh aw audit` emitted a local case-colliding-artifact extraction warning, then
retried individual artifacts and completed successfully. The reported audit
metrics above are therefore actual retrieved data.

## 2026-08-11 friction-routing acceptance

- A controlled high-signal platform event automatically created sanitized
  process issue [#126](https://github.com/lehard/dev-platform/issues/126).
  Its raw local evidence was omitted from the GitHub body.
- A repeated controlled event originally exposed that GitHub full-text search
  does not reliably index HTML-comment markers. The router was corrected to
  inspect the bounded open-issue set directly. The false duplicate #127 was
  closed with an explicit consolidation note; a third controlled occurrence
  automatically appended its bounded occurrence to #126, proving the final
  fingerprinted-upsert path.
- Unit coverage exercised project/platform destinations, redaction, open-issue
  dedupe, closed-history behavior (a closed issue is absent from the open-only
  lookup), unauthenticated fallback, later retry, and both `none` and positive
  completion checkpoints. Routing failure remains non-blocking for publication.
- The current task checkpoint was resolved positively with local structured
  event `dbdbc3ffea2f`, routed to #126.

## 2026-08-12 mandatory post-task retrospective (tasks 3.7-3.12, 5.8-5.11)

The 2026-08-12 issue revision strengthened the checkpoint from a bare
`none | one event` value into a required post-task retrospective. The
completion identity extension lives entirely in
`template/scripts/agent_friction.py`; `finish_task.py`'s call site
(`run_friction_retry_and_checkpoint` -> `assert-checkpoint`) is unchanged,
so the stronger contract applies through the exact boundary already used for
task 3.2's original checkpoint.

- `checkpoint --result none` still means a clean run, but is now rejected if
  combined with `--event`; `checkpoint --event <id>` is repeatable, so one
  retrospective can reference `0..N` existing recorded friction events
  (already-recorded findings) without creating duplicates. A candidate
  resolved during the task is simply never referenced -- no CLI call, no new
  state.
- The stored checkpoint now binds `branch` + current Git `head`.
  `require_checkpoint`/`assert-checkpoint` reject a checkpoint whose recorded
  head no longer matches the branch's current head, so a stale receipt from
  earlier work cannot silently satisfy new commits; the rejection message is
  actionable (tells the agent to rerun the retrospective).
- `require_checkpoint` also rejects a checkpoint that references a friction
  event id no longer present in the local log, without ever inventing `none`
  on the agent's behalf.
- Referenced findings whose GitHub routing is still `pending` (auth/network
  failure) still satisfy completion: only local existence is checked, so
  routing failure remains non-blocking for otherwise safe publication.
- `tests/test_friction_review.py` gained 8 new cases exercising this
  end-to-end through the real `cmd_checkpoint`/`require_checkpoint` functions:
  multiple findings in one retrospective, unknown-id rejection, `none`
  combined with findings rejected, missing-argument rejection, stale-head
  rejection, fresh-after-new-commit acceptance, already-recorded reference
  creating no duplicate, pending-routing-failure tolerance, and
  no-managed-provenance-required (quick-task) behavior. All 20 cases in that
  module pass; see task 5.8-5.11 evidence pointers in `tasks.md`.
- Generated guidance (`AGENTS.md`, `template/AGENTS.md.jinja`) now documents
  the retrospective as a distinct semantic pass -- inspect signal classes,
  classify resolved / already-recorded / new-unresolved, record only the
  last class -- and states the final report must truthfully say the
  retrospective ran and list findings or say none were found.

## 2026-08-12 truthful bounded execution provenance (tasks 6.1-6.11)

The 2026-08-12 execution-provenance revision (merged via PR #209, authoring
only) added section 6 to this change. All items are implemented and tested
except real Codex-leg acceptance, which is externally blocked.

**Preflight (6.1), against the actual current runtime, not assumptions:**

- Codex: `codex exec --json --sandbox read-only --skip-git-repo-check -m
  gpt-5.6-terra "Reply with exactly: OK"` was run live in an isolated
  scratch git repository. It emitted `{"type":"thread.started","thread_id":
  "019ff7be-6e9d-7110-98bb-2591886d55d1"}` before the account's usage limit
  cut the turn short (`"You've hit your usage limit... try again at Aug
  18th, 2026 7:52 AM"`). `thread_id` is therefore a confirmed, real, bounded
  execution identifier; no field in the documented `--json` stream confirms
  effective model/reasoning-effort for a turn -- internal `codex.turn.
  reasoning_effort` OpenTelemetry span attributes exist in the compiled
  binary (`strings` inspection) but require undocumented OTel wiring, so
  they are deliberately not used as a supported surface.
- Claude Code: the actual `Agent` tool's parameter schema (read directly,
  not inferred) is `description, isolation, model, prompt, run_in_background,
  subagent_type` -- no `effort`. `model_routing.py`'s `claude_agent()` had
  been silently emitting a fabricated `"effort": "medium"/"high"` and
  `"maxTurns": 24` that the real tool never consumes; both were removed.

**Real acceptance (6.11):**

- Claude leg, done for real: `python3 scripts/dogfood_task.py route-claude
  --profile routine ...` emitted the real hand-off (`model: haiku`); the
  exact hand-off was invoked as an actual `Agent` tool call (not simulated)
  for a bounded, read-only verification task; it returned agent id
  `a7238c3adade4fd10`; `python3 scripts/model_routing.py
  record-claude-execution --agent-id a7238c3adade4fd10 ...` produced:
  `participant.model = {"value": "haiku", "source": "selected"}`,
  `participant.reasoning_effort = {"value": null, "source": "unknown"}`,
  `participant.execution_id = {"value": "a7238c3adade4fd10", "kind":
  "claude-agent-id"}`, `postcheck.containment = "clean"`. The delegated
  child's first attempt read stale content from the wrong absolute path
  (the main checkout instead of the assigned worktree) despite its actual
  `pwd`/`git rev-parse --show-toplevel`/`branch`/`HEAD` all being correct;
  it self-corrected once asked for raw diagnostics, then confirmed all 5
  documentation claims accurate against the real code. That near-miss is
  itself now sanitized process evidence: `lehard/dev-platform#213`. This
  run was performed on a real routing record and then reverted (the
  worktree's actual routing record was restored to the correctly-recorded
  `complex` decision for the main implementation work afterward) so it does
  not misrepresent how the substantive implementation was actually done.
- Codex leg: not completed. The authenticated Codex account is credit-limited
  until 2026-08-18T07:52 (confirmed live during the 6.1 preflight run
  above, not assumed or estimated). A genuine routine/standard Codex
  delegation with a real `thread_id` capture cannot happen before then.

**Other findings from this work, sanitized and routed:**

- `lehard/dev-platform#200` -- no recovery path existed for OpenSpec
  changes materialized before `.managed-task.json` provenance enforcement
  (discovered while resuming this very task).
- `lehard/dev-platform#204` -- `AGENTS.md`'s documented central-repo
  `managed_task.py owner/repo#N` command unconditionally fails on this
  repo's own integration checkout; fixed in the relocated
  `docs/engineering/agent-workflow.md`.
- `lehard/dev-platform#205` -- no first-class command to abandon a started
  but non-viable quick task.
- `lehard/dev-platform#213` -- the Claude hand-off near-miss described above.

## Remaining acceptance work

- Observe a real scheduled weekly run; the workflow's manual dispatch has been
  verified, but the scheduled half of task 5.6 has not yet occurred. Nearest
  expected slot per the 2026-08-11 checkpoint comment on
  `lehard/development-backlog#5`: 2026-08-13 22:25 UTC.
- Task 5.12 (truthful final-report retrospective statement) is satisfied by
  this task's own terminal report, not by a unit test; it closes when this
  task actually completes.
- Task 6.11's Codex leg: blocked until the account's usage limit resets on
  2026-08-18T07:52. Re-run the same live preflight command in
  `run_codex()`'s real path (a genuine routine/standard `dispatch-codex`
  call) once credits are available, and record the resulting real
  `thread_id`/participant evidence here.
- Before archival, perform the full semantic OpenSpec verification and then
  record its truthful verification receipt. This active change is still not
  ready to archive or release: 5.6, 5.12, and 6.11's Codex leg remain open,
  and archival cannot precede them.
