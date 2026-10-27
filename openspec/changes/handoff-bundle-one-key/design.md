## Decisions

- **Key = handoff id.** The handoff file name (intent id, or `direct`) is the only name pre-authoring guarantees and the one materialization already uses for `bundles/<key>`. Change names come from the bundle's `change`. The handoff format is not touched (BR exclusion), so the alternative binding lives in the bundle manifest: an optional `"handoff"` field, which the managed bundle loader ignores.
- **No coincidental pairing.** A bundle named after the change is never matched to a handoff by name similarity; it must declare its handoff.
- **Explicit failures.** The former `except Exception: return None` around bundle loading hid both "no bundle" and "broken bundle". "No bundle for this handoff" stays a normal outcome while the handoff is not materialized; a broken or ambiguous bundle raises. The historical-child error names the unmapped handoffs when any exist.
