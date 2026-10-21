## Why

A friction record's identity is `repository + scope + category`, and the category is a free name chosen at record time. One root cause therefore spreads over many open issues (the 2026-10-11 process health review found 17 records for the `TBD` Purpose placeholder, 12 for TMPDIR outside reviewed roots, 9 for the false duplicate guard). The router already detects likely same-root records (`likely_duplicate_candidates`) and stops in a `candidate` route state, but nothing resolves that state: the event stays local forever and agents re-record it under a new name (open record #405 `friction-duplicate-decision-dead-end`). Separately, fixes close only the evidence they are explicitly linked to, so symptoms of a fixed root stay open; inflow is about 18 issues a day against 28 closed before the review.

## What Changes

- A friction issue records every fingerprint that belongs to its root as a marker in its body. Routing matches an event's fingerprint against all markers, so once a category is attached to a root, later events of that category go straight to the root issue as occurrences.
- New `agent_friction.py resolve-candidate --id <event> (--same-root owner/repo#N | --new-root) --reason TEXT` ends the `candidate` dead end: `--same-root` adds the event as an occurrence of issue N and appends the event's fingerprint marker to N; `--new-root` creates the issue as ordinary routing would. A target that is not an open router-generated friction issue is a named error.
- New `agent_friction.py merge-roots --into owner/repo#N --duplicate owner/repo#M [...] --reason TEXT` consolidates already open duplicates of one root: the duplicates' markers move to N, N gets a comment listing them, and each duplicate is closed with a comment pointing to N. Applied to the review sample (TBD Purpose, TMPDIR, duplicate guard) as acceptance evidence.
- A fix declares the records it closes with lines `Fixes-Friction: owner/repo#N`, in its OpenSpec `proposal.md` or in the PR body. When such a PR is merged, `agent_friction.py close-fixed --pr <number>` closes each referenced open friction issue with a comment naming the PR and merge commit. A reference to an issue that is not a router-generated friction issue, a malformed reference or a cross-repository reference fails the run with a named error. Without a reference nothing is closed automatically.
- A thin `.github/workflows/friction-close-on-merge.yml` in this repository runs `close-fixed` for every merged PR.

Fixes-Friction: lehard/dev-platform#405

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: friction routing identity, explicit duplicate resolution, root consolidation and closing on fix.

## Impact

- `template/scripts/agent_friction.py` (rendered into managed projects) and its tests.
- New platform workflow `.github/workflows/friction-close-on-merge.yml` (platform repository only; not shipped to projects in this change).
- Agent workflow documentation for recording `Fixes-Friction:` references.
