# Change classes

This document tells an agent which kind of change it is making when it touches a file. It is platform-owned and arrives only through a Dev Platform release. The authoritative, machine-readable classification is [dev-platform/protected-surface.toml](../../dev-platform/protected-surface.toml); this page explains it and never overrides it.

## The three classes

| Class | What it is | Where it goes |
| --- | --- | --- |
| (a) Ordinary project change | Project-owned code, docs, configuration and OpenSpec artifacts, including the project-owned files Copier updates leave untouched (see [project-rules.md](project-rules.md)). | The normal project task, PR, CI and review. |
| (b) Temporary local hotfix | A short-lived local repair of a *hotfixable* platform-owned mechanism that keeps every guarantee of the protected rules. | The class is allowed. Its mechanism and its record are delivered by a follow-up change; do not patch a platform-owned file locally until that change is released. |
| (c) Protected rule | A platform-owned file or rule listed as protected in `protected-surface.toml`. | No local change path. It changes only through a platform release, or through a recovery path the gate itself already defines (for example an owner-recorded decision that the gate documents). |

## The protected surface

`dev-platform/protected-surface.toml` declares:

- `[categories]`: the protected rule categories, each with a one-line rationale: independent review, protected publication, isolation of other agents' worktrees, credential restrictions, routing/provenance/evidence authenticity, Git-history protection and immutable releases.
- `[[protected]]`: path globs of the platform-owned files that implement those categories, each tagged with its category. Whole script groups are protected on purpose, because a partially protected script cannot be patched safely.
- `hotfixable`: the explicit list of the remaining plain-copied platform-owned files.

Classification fails closed: every plain-copied platform-owned file is either protected or listed `hotfixable`, there is no default class, and the platform's own validation fails on a file that is neither. A file that is project-owned (kept by Copier updates) is class (a), not (b) or (c).

## What an agent never does

- Never reclassify a file or a rule, and never edit `protected-surface.toml`: neither the protected list nor the `hotfixable` list changes downstream.
- Never declare a review, publication, isolation, credential, provenance or history gate "safe to change" on its own assumption, however narrow the defect looks.
- Never bypass or weaken a protected gate with a universal override such as `--force` or by disabling a check. No such override exists in this contract.
- Never treat "not listed protected" as permission: only an explicit `hotfixable` entry makes a file eligible for class (b), and only once the follow-up mechanism exists.

## When a protected rule blocks the work

Stop and report the blocking gate, the exact command output and that the change is class (c). The fix is a Dev Platform release delivered by Copier update, or the recovery path the gate itself documents (such as an owner-recorded decision). Continue product work that does not depend on the blocked gate.

Classification is a navigation aid for the change, not a substitute for the checks, review and publication lifecycle described in [agent-workflow.md](agent-workflow.md).
