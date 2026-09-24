# Proposal: Source-bound merge candidate generations

## Why

The corrected #164 chain after required CI failure has the same main base as its failed predecessor. The existing merge-recovery generation uses only that base and refuses to create another immutable candidate.

## What Changes

New merge-recovery manifests use a generation key containing both the authoritative base SHA and exact final child SHA. Thus a corrected source receives a new candidate while the earlier PR and worktree remain untouched.
