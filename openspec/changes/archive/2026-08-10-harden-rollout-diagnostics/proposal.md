# Change: Make managed rollout failures agent-diagnosable

## Why

`allow-safe-reclaimed-rollout-recopy` already made managed rollout surface its blocking reason as a human-readable GitHub Actions annotation/summary (`Managed rollout: BLOCKED:` / `DEV_PLATFORM_CHECK_COMMAND:`). That change is complete for its own scope and is not reopened by this proposal.

The remaining gap is that an agent diagnosing a failed rollout still has no stable, structured contract to consume. It must discover workflow/job APIs, scrape arbitrary log text, or guess whether a same-input retry is safe. The rollout already computes enough structured state (stage, failing command, exit code, known conflict paths) to emit a deterministic terminal diagnostic instead of leaving that reconstruction to whoever reads the log next.

## What changes

- Introduce a canonical, versioned `rollout-diagnostic.json` envelope produced from structured rollout state for every terminal failed managed-project rollout attempt — never from arbitrary log scraping.
- Map terminal failures to stable `stage`/`category`/`reason`/`exit_code` fields, and preserve the exact selected command only from the existing `DEV_PLATFORM_CHECK_COMMAND:` marker.
- Add `retry_same_inputs = safe|pointless|unknown` as advisory metadata only; the workflow never auto-reruns, auto-merges, or auto-pushes based on it.
- Include already-known structured evidence (e.g. Copier conflict paths) while excluding tokens, environment dumps, secrets, and unrestricted raw logs.
- Render the same canonical diagnostic into the existing GitHub Actions summary/error annotation and upload a predictably named diagnostic artifact on failure.
- Make diagnostic generation/upload best-effort but failure-preserving: any failure to produce or publish the diagnostic must never hide, replace, or soften the original rollout failure, and must never convert a failed rollout into success.
- Add regression tests proving exactly one canonical diagnostic per failed attempt, correct category/stage mapping, secret exclusion, and preservation of the original failure when diagnostic presentation itself fails.

## Scope

This only adds a machine-readable diagnostic layer on top of the existing managed-rollout failure path. It does not change recovery eligibility, safety guards, branch protection, or the `allow-safe-reclaimed-rollout-recopy` recopy contract, and it does not touch that change's files. It is not a general autonomous repair engine: it does not change repository contents, rerun jobs, push branches, merge PRs, or bypass confirmation/safety gates. It only exposes already-known terminal state in a stable, additive contract.

## Success criteria

When managed rollout blocks, both a human and an agent can determine the exact terminal blocker — stage, category, reason, exit code, and (when known) the failing command — from a single canonical artifact/summary, without scraping arbitrary logs. The workflow remains failed in every case; diagnostic production never weakens fail-closed behavior, branch protection, or rollout guards, and never triggers retry/merge/push on its own.
