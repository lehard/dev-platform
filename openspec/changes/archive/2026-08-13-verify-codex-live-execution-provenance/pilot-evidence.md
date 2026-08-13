# Real Codex-leg acceptance evidence

## Scope

This evidence covers the one bounded acceptance item this change exists for:
exercising the already-implemented `dogfood_task.py route-codex` ->
`model_routing.py dispatch_codex()` -> `run_codex()` path against a real,
live `codex` CLI process, from this change's own managed task worktree
(`/Users/Shared/Workspace/dev-platform/.claude/worktrees/verify-codex-live-execution-provenance`).

## 2026-08-13 rate-limit re-check (task 1.1)

`adopt-gh-aw-process-automation`'s pilot evidence recorded the authenticated
local `codex` account as rate-limited until `2026-08-18T07:52`. That date was
not assumed here; the account was re-checked live instead:

```
codex exec --json "reply with the single word: pong"
```

returned a genuine event stream -- `{"type":"thread.started","thread_id":
"019ff9c8-1ae7-7ee0-b1ce-afcc3a76c8a1"}`, an `agent_message` item with text
`"pong"`, and `{"type":"turn.completed", ...}` -- with no rate-limit error.
The account had recovered ahead of the estimated date.

## 2026-08-13 real live delegation (tasks 1.2-1.3)

The real production entrypoint was run directly, unmodified, from this task's
worktree:

```
python3 scripts/dogfood_task.py route-codex \
  --rationale "verify-codex-live-execution-provenance: authored R2/standard, confirmed no material repo drift since authoring; codex account confirmed live (not rate-limited) via direct codex exec smoke test with real thread_id and successful turn.completed before dispatch" \
  --evidence "codex exec --json smoke test returned thread.started + turn.completed with real thread_id, no rate-limit error"
```

This confirmed the authored `R2` tier as `standard` (freshness check, no
`--profile` override) and launched a real Codex executor. The resulting
`.claude/model-routing/verify-codex-live-execution-provenance.json` route
record shows:

```json
{
  "execution": {
    "launched": true,
    "mechanism": "codex-workspace-write-sandbox",
    "participant": {
      "execution_id": { "kind": "codex-thread", "value": "019ff9c9-daac-7fb2-a730-e7b96343606f" },
      "model": { "source": "selected", "value": "gpt-5.6-terra" },
      "profile": "standard",
      "provider": "codex",
      "reasoning_effort": { "source": "unknown", "value": null },
      "role": "executor"
    },
    "returncode": 0,
    "violation": false
  }
}
```

This is a real, non-fabricated `execution_id.value` (Codex thread id),
`model.source: "selected"` with the actual configured executor model, a
truthful `reasoning_effort.source: "unknown"` (no stronger surface was found
-- see below), and a clean `returncode: 0` / `violation: false`. Task 1.3's
acceptance criteria are met by this record as persisted on disk.

## No stronger model/effort surface found (task 1.4)

The dispatched executor's own turn did not surface any stronger
runtime-confirmed model or reasoning-effort signal than the 2026-08-12
preflight already found. `reasoning_effort.source` remains truthfully
`unknown`. No correction to `adopt-gh-aw-process-automation`'s
pilot-evidence.md is needed.

## Observed near-miss: nested Codex-in-Codex dispatch is denied

The dispatched executor read the materialized OpenSpec package and
interpreted its own bounded task scope as this change's task 1.2 itself --
i.e. it attempted to run `dogfood_task.py route-codex` a second time,
*nested inside its own sandboxed session*, to perform the acceptance run
itself. That nested attempt failed before any JSON event was emitted:
`failed to initialize in-process app-server client: Operation not permitted
(os error 1)`. `codex login status` inside that same nested session still
reported `Logged in using ChatGPT`, confirming this was a sandbox-depth
limitation (nested Codex cannot itself launch a further sandboxed Codex
child in this environment), not a rate-limit or authentication condition.
The executor correctly declined to fabricate a passing result for its own
nested attempt and reported the block truthfully, then ran
`python3 -m unittest tests.test_model_routing` (26 passed) as a baseline
check before ending its turn.

This is not a defect in `run_codex()`'s `--json` parsing path -- the parser
worked correctly for the real (outer, non-nested) invocation above, which is
the actual acceptance evidence this change requires. The nested self-dispatch
was an artifact of this specific change's task being self-referential (its
own bounded scope is "run the live delegation path"), not a general product
defect, so no fix is in scope here per this change's design.md decision #2
(no defect found in the parser under test).

## Result

Real, live, non-simulated Codex provenance capture through the production
`route-codex` path is proven: a genuine `thread_id`, the actual selected
executor model, and a truthful `unknown` reasoning-effort source, all
persisted in the real route record. No runtime/template code changed as part
of this acceptance run.
