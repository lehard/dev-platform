#!/usr/bin/env python3
"""Selected checks for the central repository.

Resolves the changed-file base by the selector's own rule before anything runs,
runs the shared selector unchanged, then surfaces stale Explorer editorial
explanations that touch the files changed since that base. Drift is advisory:
it never changes the selector's exit code. A failure of the drift command itself
(a tool error, not drift) is reported and fails this wrapper.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from source_adapter import run_template

ROOT = Path(__file__).resolve().parents[1]


def drift_base(argv: list[str]) -> str | None:
    """The base the drift report uses, resolved before the selector runs; ``None`` when no report applies."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--base")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--mode", default="local-affected")
    parser.add_argument("--protected-full", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--execute", action="store_true")
    known, _ = parser.parse_known_args(argv)
    if not known.execute or known.protected_full or known.full or known.mode == "protected-full":
        return None  # a protected-full run has no changed-file set to relate drift to
    sys.path.insert(0, str(ROOT / "template" / "scripts"))
    from _platform_common import resolve_changed_file_base

    base = resolve_changed_file_base(ROOT, known.base, known.changed_file)
    if base is None:
        raise SystemExit("Explorer editorial drift report needs --base <ref> together with --execute and --changed-file")
    return base


def surface_explorer_drift(base: str) -> int:
    """Print stale editorial nodes touching the changed files; return a non-zero code only on a tool error."""
    command = [sys.executable, str(ROOT / "scripts" / "build_explorer.py"), "drift", "--base", base]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"Explorer editorial drift report failed (exit {result.returncode}): {result.stderr.strip()}", file=sys.stderr)
        return result.returncode
    if result.stdout.strip():
        print("Explorer editorial drift (warning only; update the node text if needed, then run "
              "`python3 scripts/build_explorer.py mark-reviewed <node>`):")
        print(result.stdout.rstrip())
    return 0


def main() -> None:
    base = drift_base(sys.argv[1:])
    code = 0
    try:
        run_template("select_checks.py")
    except SystemExit as exit_request:
        code = exit_request.code
    if base is not None:
        drift_code = surface_explorer_drift(base)
        if drift_code and not code:
            code = drift_code
    raise SystemExit(code)


if __name__ == "__main__":
    main()
