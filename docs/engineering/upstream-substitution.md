# Upstream substitution gate

This document is the operating guidance for evaluating an external
agent-infrastructure upstream as a substitute for Dev Platform's own
implementation. The accepted behavior lives in the `upstream-substitution`
OpenSpec capability
([openspec/specs/upstream-substitution/spec.md](../../openspec/specs/upstream-substitution/spec.md));
this page explains how to run a pilot and record its decision.

## When the gate applies

Use this gate when an external tool overlaps something Dev Platform already
implements or would otherwise build: for example syncing skills, rules, hooks,
MCP servers or model profiles, storing team learnings, indexing codebases, or
providing analytics dashboards.

It does not apply to agent execution runtimes. Runtime backends stay under the
`agent-runtime` capability (`openspec/specs/agent-runtime/spec.md`) and its
compatibility pilots; see
[deepseek-harness-runtime.md](deepseek-harness-runtime.md) for that precedent.
Both gates share one decision vocabulary: `adopt-next-step`, `watch-only`, or
`reject-for-now`.

The unit of decision is one **overlapping capability**, not the whole tool. An
upstream may be adopted for one area and rejected for another, and an adoption
for one capability never authorizes another.

## Pilot procedure

1. **Pin the candidate.** Evaluate the exact current stable release. A
   prerelease may be read as roadmap evidence only; it never becomes the
   evaluated default, and a capability seen only in a prerelease cannot be
   recorded as `adopt-next-step`.
2. **Build the sandbox** using the checklist below, and snapshot it before the
   first scenario.
3. **List the overlapping capabilities** and, for each, the Dev Platform code,
   tests, docs and workflow steps it overlaps.
4. **Measure the maintenance-surface baseline** of that own implementation
   (source, tests and documentation lines at the evaluated revision) before
   running any scenario.
5. **Run the required scenarios** and record observed behavior, not upstream
   self-reports or desk research.
6. **Diff the sandbox** against the snapshot and confirm nothing escaped it.
7. **Write the decision record** and have it reviewed. Dev Platform acceptance
   judges the result.

### Sandbox isolation checklist

- [ ] Isolated `HOME` and tool-install prefix dedicated to the pilot.
- [ ] Local disposable repositories only; no real managed project is touched.
- [ ] Create local disposable repositories with
      `python3 scripts/disposable_repository_sandbox.py create <source> <sandbox-root> <name>`.
      Before a supported recursive cleanup, run the corresponding `verify`
      (or use `cleanup`, which verifies first). The helper requires its
      ownership marker, rejects hardlinked files, alternates, linked Git
      metadata and symlink escapes, and fails closed without a best-effort
      cleanup fallback. `git clone --no-hardlinks` or `git archive` are only
      acceptable when equivalent Git/filesystem isolation has been proved;
      never use a plain `git clone --local`.
- [ ] No real credentials, tokens or accounts; use keyless or fixture backends.
- [ ] Upstream self-update, shell-profile injection, automatically applied
      hooks or MCP servers, and outbound usage reporting are disabled, unless a
      scenario explicitly measures one of them inside the sandbox.
- [ ] No writes to shared operator configuration (real `~/.claude`, `~/.codex`,
      shell profiles, global git config), to other agents' worktrees, or to the
      integration checkout.
- [ ] A before/after diff of the sandbox and of the protected operator
      locations is captured; unexpected writes are recorded as findings.
- [ ] The sandbox is deleted after the record is written.

### Required scenarios

- At least one representative Dev Platform workflow that exercises the
  overlapping capability.
- At least one managed-project scenario rendered freshly from the current
  template, with the agent surfaces in use (Claude Code and Codex today).

## Decision record

Write one durable record per upstream evaluation at
`docs/engineering/upstream-evaluations/<upstream>.md`. A later evaluation of the
same upstream updates that record with a new dated section rather than creating
a competing file.

For a consequential platform-wide conclusion, also write a concise historical
decision in the [decision registry](../decisions/README.md) and link this
evaluation as its detailed evidence. A later changed conclusion gets a new
registry record with an explicit supersession link; keep the evaluation's
dated pilot evidence and per-capability decisions intact. The registry does
not authorize adoption or replace the OpenSpec contract.

Template:

```markdown
# <Upstream> substitution evaluation

- Evaluated version: <exact stable release> (<date>)
- Prerelease observations (roadmap evidence only): <none | notes>
- Dev Platform revision: <commit>
- Sandbox: <how HOME/prefix were isolated; mutating defaults disabled>
- Sandbox diff result: <clean | findings>
- Scenarios: <Dev Platform workflow>; <fresh managed-project render + surfaces>

## Capability: <name>

| Field | Evidence |
| --- | --- |
| Decision | `adopt-next-step` / `watch-only` / `reject-for-now` |
| Observed behavior and acceptance outcome | |
| Lifecycle coupling | |
| Migration cost | |
| Release cadence and churn | |
| Security and privacy (what leaves the machine, command surfaces) | |
| Failure and rollback behavior | |
| Codex / Claude compatibility | |
| Ownership classification | direct / thin adapter / Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | |
| Retirement set (adopt) or retention evidence (keep) | |
| Projected maintenance reduction (adopt) | |
```

Repeat the capability section for every overlapping capability. A measurement
that could not be taken stays `unknown`; it is never inferred or zeroed.

"We already have one" is not a valid retention reason. A record that keeps the
Dev Platform implementation must name the compatibility, risk or coupling
evidence that prevents substitution; otherwise it fails review. Likewise, an
`adopt-next-step` must name the concrete own code, workflow steps, tests and
docs it retires, with their measured size.

## Adoption constraints

An `adopt-next-step` authorizes only a separately authored managed change. That
change must:

- integrate the upstream as an opt-in capability or thin adapter (see
  [engineering-capabilities.md](engineering-capabilities.md)), pinned to the
  exact upstream version and the exact reviewed revision of any
  upstream-distributed resources;
- disable, or prove containment of, upstream self-update and mutable
  default-branch pulls, so managed-project behavior changes only with a new
  Dev Platform release;
- reach managed projects only through an immutable Dev Platform release and
  controlled rollout, with rollback to the prior release (see
  [release-policy.md](../release-policy.md));
- retire the superseded own mechanism in the same delivery, or record a bounded
  transitional exit criterion; two mechanisms with the same responsibility do
  not remain without one; and
- re-verify the lifecycle core listed below.

## Non-transferable core

A substitution decision never transfers ownership of:

- the requirement-first and OpenSpec lifecycle;
- managed task identity;
- writer and worktree containment;
- verification and publication;
- immutable release and controlled rollout.

If an upstream capability only works when its own task, specification or
completion state becomes authoritative for any of these, record that as
negative coupling evidence; the capability cannot be `adopt-next-step`.
Proposing to move any part of this core requires its own evidence-based change,
which this gate does not authorize.
