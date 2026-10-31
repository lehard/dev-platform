## Why

Measured 2026-10-31 on the operator Mac: one `work-next` for post-merge kinds spends 160 s before any work (dry run): 133 `gh` reads (about 109 s) because it reads the comments of every candidate (~90 PRs) and `pulls/N` of every unsettled labeled PR, plus 42 s re-parsing the 29 MB GitHub read cache on every read. Selection is ascending by PR number, so 52 unsettled PRs from early October (#324-#460) are served before #808-#821, whose retrospectives waited 3-11 hours. The runner kills a run at the remaining round budget: 44 of 78 rounds ended `failed: ... exceeded Ns and was killed`. Composition terminal reconciliation of PR #362 failed three times with `.dev-platform.toml is missing required key agent_tools`: the historical head's public contract predates the key.

## What Changes

- Post-merge offer order: open PRs first (pre-merge composition retrospective), then merged PRs by merge time, newest first. Other kinds keep ascending order.
- Lazy selection: `work_next` derives candidates one by one in offer order and stops at the first claimable job; a PR known only from the `lifecycle:merged` label listing is read (`pulls/N`) only when reached. An idle run still derives every candidate, so settled labeling and the `skipped` failure stay as they are.
- Discovery and the lifecycle overview skip a closed PR already labeled `post-merge:settled` in the recent page too.
- The GitHub read cache keeps the parsed file in process memory and reloads it when the file's mtime or size changed.
- Post-merge runner: no new run starts after the deadline; a started run's timeout is the claim TTL; reaching the deadline ends the round `max-seconds`.
- Composition post-merge checkouts (terminal gate check and manifest read) install the integration checkout's `.dev-platform.toml` instead of the head's own public contract.

## Impact

- `scripts/post_merge_runner.py`, `template/scripts/{lifecycle_workers,github_read_cache,requirement_composition,integration_contour}.py`, tests, platform manifest.
- Spec: lifecycle-workers (requirements added).
- Thresholds (approved ADD): fresh obligation selection at most 15 s at the current candidate volume; idle run at most 15 s once the tail is settled; median no-op action over a day at most 45 s (now 220 s).
