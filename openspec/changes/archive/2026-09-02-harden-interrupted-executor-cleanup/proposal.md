# Proposal: Harden externally interrupted executor cleanup

## Why

The delegated writer already has process-group containment, but an external termination of the Python launcher can bypass normal exception cleanup and leave a write-capable orphan without a trustworthy handoff.

## What Changes

- Convert supported external interruption signals into the existing controlled abnormal-return path.
- Reap the full delegated process group before releasing writer ownership.
- Persist a bounded classified abnormal receipt and retain ambiguous ownership when absence cannot be proven.
- Preserve partial work without retrying or judging it automatically.
