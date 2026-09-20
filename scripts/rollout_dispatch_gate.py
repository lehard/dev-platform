"""Whether the release workflow should dispatch managed-project rollout.

Release publication is a core Dev Platform product capability; managed
fleet rollout is an optional operator capability that must never be
implied merely by publishing a release. Dispatch requires an explicit
operator opt-in via a repository *variable* -- never a secret, since a
secret's mere presence must not double as a feature flag.
"""
from __future__ import annotations

import os
import sys

ENV_VAR = "DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED"


def rollout_dispatch_enabled(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "true"


def main() -> int:
    enabled = rollout_dispatch_enabled(os.environ.get(ENV_VAR))
    if enabled:
        print(f"Managed rollout is enabled for this repository via {ENV_VAR}.", file=sys.stderr)
    else:
        print(
            "Managed rollout is disabled/not configured for this repository; skipping dispatch.",
            file=sys.stderr,
        )
    print(f"dispatch={'true' if enabled else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
