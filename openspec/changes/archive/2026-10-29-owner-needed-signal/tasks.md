# Tasks

## 1. Contract

- [x] Specify the signal contract, task identity rules, de-duplication and resolution in the two spec deltas.

## 2. Implementation

- [x] Add the signal command with raise and resolve, storage on the board entry under the board lock, and explicit errors.
- [x] Add the "Owner needed" section to `lifecycle_overview.py` (text and JSON) with the unconfigured and unreadable lines.
- [x] Add the source wrapper, protected-surface classification and manifest, and document the command and the coordinator line.

## 3. Verification

- [x] Test raise, repeat, resolve, re-raise, missing/finished/foreign task, missing capability, task-end cleanup and the overview output.
- [x] Run affected and full platform checks, semantic OpenSpec verification, and archive with truthful receipt.
