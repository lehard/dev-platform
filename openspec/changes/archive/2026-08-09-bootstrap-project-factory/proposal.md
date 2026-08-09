# Bootstrap the shared project factory

## Why

Reusable engineering process has matured inside Jara_Fin, while other repositories already show process drift. Copying rules and helper scripts manually will not scale and makes future improvements expensive to propagate.

## Goals

- Create a central, versioned project factory.
- Extract only reusable workflow: agent lifecycle, OpenSpec policy, worktrees, agent board, merge safety, checks, friction loop and GitHub CI.
- Support both creating new repositories and updating existing ones.
- Keep project/domain rules outside the platform-managed layer.
- Keep OpenSpec-generated tool integrations external to the platform.

## Non-goals

- Move Jara_Fin financial rules or domain architecture into the platform.
- Standardize every application stack in the first iteration.
- Automatically modify every existing repository without review.
- Build a full internal developer portal.

## Acceptance

A new repository can be rendered with Copier, contains the shared workflow, can initialize OpenSpec for Claude/Codex when the CLI exists, and has deterministic local coordination/merge/check/friction tools. Existing projects have an explicit update path.
