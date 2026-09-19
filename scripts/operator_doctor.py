"""Validate explicit external operator state without copying it into source."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import managed_projects


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate explicit external Dev Platform operator configuration.")
    parser.add_argument("--registry", type=Path, help="Registry override; otherwise resolve from the explicit operator config.")
    args = parser.parse_args()
    try:
        path = managed_projects.configured_registry(args.registry)
        managed_projects.load_registry(path)
    except ValueError as exc:
        print(f"Operator configuration: BLOCKED: {exc}")
        return 2
    print(f"Operator configuration: OK (registry: {path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
