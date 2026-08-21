# Proposal: Standard-profile lifecycle compatibility contract

## Current state

The platform documents `standard` as a supported profile with isolated full
task clones, but the v1.4.36 rollout exposed two mismatches: managed intake
expected a callable task-start API absent from the standard wrapper, and
routing preflight assumed a multi-agent linked-worktree topology. Downstream
patches restored both paths after release.

## Target state

The shared/template lifecycle defines and tests a stable standard-profile
task-start interface and parent-only routing semantics. A deterministic
consumer compatibility suite validates managed discovery/start and routing
preflight against a rendered/adopted standard-profile checkout before release
or rollout publication.

## Scope and non-goals

This is universal platform behavior for existing managed downstream projects
and newly generated projects. It does not change project-owned product rules,
does not permit child writers in the integration clone, and does not add a
service, credentials, or real agent execution to tests.

## Success evidence

The test matrix passes for `light`, `standard`, and `multi-agent`, with a
specific standard consumer case proving callable start and parent-only routing.
An incompatible template or profile topology fails before downstream rollout.

## Downstream compatibility

Affected rendered files and template helpers must roll out through the normal
Copier path. Existing downstream compatibility overrides should be removable
only after an update proves the shared contract supplies their behavior.
