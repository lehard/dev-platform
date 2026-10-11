# Change classes

This document tells an agent which kind of change it is making when it touches a file. It is platform-owned and arrives only through a Dev Platform release. The authoritative, machine-readable classification is [dev-platform/protected-surface.toml](../../dev-platform/protected-surface.toml); this page explains it and never overrides it.

## The three classes

| Class | What it is | Where it goes |
| --- | --- | --- |
| (a) Ordinary project change | Project-owned code, docs, configuration and OpenSpec artifacts, including the project-owned files Copier updates leave untouched (see [project-rules.md](project-rules.md)). | The normal project task, PR, CI and review. |
| (b) Temporary local hotfix | A short-lived local repair of a *hotfixable* platform-owned mechanism that keeps every guarantee of the protected rules. | Allowed through the [hotfix flow](#temporary-local-hotfix-flow) below: ordinary project PR, CI and independent review plus a declared, regression-tested, temporary record. |
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
- Never treat "not listed protected" as permission: only an explicit `hotfixable` entry makes a file eligible for class (b), and only through the hotfix flow below.

## Temporary local hotfix flow

A reproducible defect in a `hotfixable` platform-owned file may block a project until the next immutable release. Class (b) lets the project repair it locally and temporarily, only like this:

1. Reproduce the defect and confirm the file is listed `hotfixable` in `protected-surface.toml`. A protected file, a project-owned file or a templated file is not eligible; stop and report class (c).
2. Patch only that hotfixable file, narrowly, inside the ordinary project task and PR. Never edit `protected-surface.toml`, `platform-manifest.json`, `platform_divergence.py` or `platform_doctor.py`.
3. Add a regression test that fails without the patch and passes with it.
4. Record the defect with `python3 scripts/agent_friction.py record ...` so the platform learns of it, and keep the printed event id.
5. Add a `[[hotfix]]` entry to the project-owned `dev-platform/local-hotfixes.toml` with `path`, `platform_version` (the installed `.dev-platform.toml` version), `patched_sha256` (the sha256 of the patched file), `defect`, `regression_test`, `friction_event` and `temporary = true`. The file survives Copier updates; its header lists the fields.
6. Open the ordinary PR. Required checks and independent review run unchanged and judge whether the patch is bounded and the regression test really exposes the defect.

A hotfix is temporary and is not an official release: the installed platform release is unchanged. It expires on the next platform update, after which its entry is reported stale until a human or agent re-evaluates it (usually by deleting the entry once the release carries the fix). Report the defect upstream through the friction event rather than keeping the patch.

### Divergence check

`python3 scripts/platform_divergence.py` compares every platform-owned file with `dev-platform/platform-manifest.json` (the release's sha256 per file) and with the record. `scripts/platform_doctor.py` runs it, and a project may also add it to the `full_commands` of its own project-owned `dev-platform/checks.toml`. It exits non-zero and prints `[class] path: message` for each problem:

| Class | Meaning |
| --- | --- |
| `undeclared-divergence` | A hotfixable file differs from the manifest (or is missing) and no record entry covers it. |
| `protected-touch` | A protected file differs from the manifest, or an entry names a protected path. There is no local change path. |
| `unknown-path` | An entry names a path that is not in the manifest. |
| `stale-hotfix` | The entry was made against another platform version than the installed one. The check never edits the record. |
| `digest-mismatch` | The recorded `patched_sha256` is not the file's current digest. |
| `missing-regression-test` | The named regression test file does not exist. The check proves presence only, not adequacy. |
| `missing-friction-event` | The friction event id is not in the machine-local friction log, or that log cannot be read. The log is machine-local, so run the check where the event was recorded. |
| `invalid-record` | The manifest, protected surface, config or record is missing, malformed or has a missing or unknown field. |

The check is local and compares files with a local manifest: an agent that edits a protected file and the manifest consistently is not detected by it. The Copier update diff against the released template and independent PR review detect that, and they stay mandatory.

## When a protected rule blocks the work

Stop and report the blocking gate, the exact command output and that the change is class (c). The fix is a Dev Platform release delivered by Copier update, or the recovery path the gate itself documents (such as an owner-recorded decision). Continue product work that does not depend on the blocked gate.

Classification is a navigation aid for the change, not a substitute for the checks, review and publication lifecycle described in [agent-workflow.md](agent-workflow.md).
