## Decisions

- **No speed assertions.** A test may bound how long it waits (a hang detector) but SHALL NOT pass only if the machine is fast. Upper windows that must not expire use `process_deadline_seconds()` / `wait_for_readiness` from `tests/_concurrent_lifecycle.py`; lower bounds on elapsed time are replaced by ordering evidence.
- **Ordering instead of elapsed time.** The lock holder writes a release marker immediately before releasing; the serialized step records whether the marker exists when it runs. Without waiting for the lock the marker is absent.
- **Liveness instead of racing sleeps.** The grandchild writes its pid on start and then sleeps far longer than the test; after the launcher timeout the test waits within the bounded deadline for that pid to disappear. A grandchild that never started fails explicitly.
- **Proof.** The affected test modules are run repeatedly while CPU-burning processes oversubscribe every core (`yes > /dev/null` per core times several), with zero failures recorded in verification. Parallelism, pool and product timeouts are unchanged.
