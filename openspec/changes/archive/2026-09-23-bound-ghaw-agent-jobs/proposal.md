# Proposal: bound-ghaw-agent-jobs

## Why

The post-merge audit of Requirement #161 found that generated gh-aw agent jobs lack `jobs.agent.timeout-minutes` although the agentic execution steps have a 8–10 minute timeout. A hung setup or cleanup step can therefore consume the platform job default.

## Outcome

The three platform-owned gh-aw workflows declare explicit whole-agent-job deadlines in their canonical source and compiled locks. A focused regression fails if any generated agent job loses its deadline.

## Scope

The three gh-aw sources and their generated locks, the gh-aw compiler pin, focused regression, and CI safety specification. Keep existing permissions and step timeouts. The compiler pin must advance because v0.85.4 silently omits `jobs.agent.timeout-minutes` from generated locks.
