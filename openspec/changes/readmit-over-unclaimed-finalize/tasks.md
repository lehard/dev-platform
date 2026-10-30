## 1. Queue
- [ ] 1.1 Add `finalize-pending` to `READMISSION_STATES` and `DEVELOPER_FIX_STATES` in `publication_queue.py`; update their comments.

## 2. Tests
- [ ] 2.1 Supersession accepts an unclaimed finalize-pending candidate at a descendant head and refuses a live finalize claim, a non-descendant head and another task.
- [ ] 2.2 `local_status` observes and `semantic_readmission` re-opens the archived handoff for finalize-pending; regenerate the platform manifest.

## 3. Verification
- [ ] 3.1 Full validation and semantic OpenSpec verification.
