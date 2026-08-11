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

## Remaining acceptance work

- Observe a real scheduled weekly run; the workflow's manual dispatch has been
  verified, but the scheduled half of task 5.6 has not yet occurred.
- Before archival, perform the full semantic OpenSpec verification and then
  record its truthful verification receipt. This active change is not ready to
  archive or release yet.
