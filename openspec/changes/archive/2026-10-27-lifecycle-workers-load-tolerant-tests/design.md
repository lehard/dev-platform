## Decisions

- **Observe the process, not the clock.** A child writes its pid atomically (`.tmp` then `os.replace`) and then sleeps 600 s before its late write. The parent waits for the pid file before it exits, so the group kill always meets a live child, and the test polls `os.kill(pid, 0)` until `ProcessLookupError` within `process_deadline_seconds()`; a survivor is killed and the test fails naming it.
- **Pipe holder.** `run_in_session` gets `timeout=process_deadline_seconds()`: if a stdout-holding child kept it waiting, the 600 s sleep would exceed the deadline and the call raises `TimeoutExpired`, failing the test.
- **No retries, no product change.** `lifecycle_workers.py` is unchanged; only the tests and the fake writer script inside the test module change.
