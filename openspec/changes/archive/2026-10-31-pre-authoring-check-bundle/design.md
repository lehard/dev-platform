## Context

`managed_task.validate_authoring_bundle(root, bundle, target_repository, prepared_against)` writes the package into a temporary change on an exact-revision checkout and runs `openspec validate <change> --strict`; `create_task` calls it after `target_main(root)` and before any Issue. `execute_requirement._bundle(base_dir, requirement, handoff)` resolves a handoff's bundle (directory named by the handoff id, or the single bundle whose manifest declares it). The direct handoff uses `bundles/direct`.

## Decisions

- **Command.** `check-bundle` in `orchestrate_pre_authoring.py`: requires the status to be `complete` (else fails naming the current stage), takes the handoff ids from the status report (`direct` or intent ids), resolves each bundle with `execute_requirement._bundle`, loads it with `managed_task.load_authoring_bundle`, reads the target repository from the selection and `prepared_against = managed_task.target_main(root)`, and runs `validate_authoring_bundle`. A missing or ambiguous bundle fails explicitly naming the handoff. Output: `check-bundle: <handoff> <change>: valid` per bundle; the first failure re-raises the OpenSpec output.
- **No coupling to advance.** Nothing is recorded; advance does not read any result of `check-bundle`.
- **Status.** The complete report gains `"bundle_check": "orchestrate_pre_authoring.py --id <id> check-bundle (optional)"`; no file or CLI is touched.

## Risks

- The check fetches `origin/<main>` like advance does; a main that moves before advance can still make advance fail, which advance reports as today.
