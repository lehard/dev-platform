## Why

Disposable copies made with local Git hardlinks can share object inodes with an integration checkout. Recursive permission repair in the copy then mutates the integration object store. Guidance currently names `git clone --no-hardlinks` for substitution pilots, but no supported runtime path proves the boundary before cleanup.

## What Changes

- Add one repository-owned command to create, verify, and remove disposable Git repository copies under an explicit sandbox root.
- Refuse operations when the copy contains shared Git objects or metadata, escapes its allowed root, or has unprovable ownership.
- Align agent instructions and sandbox guidance with that command.
- Add regression tests around hardlinked objects and safe cleanup.

## Impact

This adds a supported local sandbox workflow for platform and managed projects without changing ordinary Git clone behavior or introducing a new runtime.
