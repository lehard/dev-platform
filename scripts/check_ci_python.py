#!/usr/bin/env python3
"""Compile the platform's Python sources on the Python version that CI pins.

Source-only validation step of the full local check set. Local checks run on the
``python3`` found on PATH, while CI pins one version in its validation workflow; a
source that compiles locally can still fail there (for example the Python 3.11
limit on statically nested blocks). This step reads the version from the single
``actions/setup-python`` step of the named workflow job. When the running
interpreter has the same ``major.minor`` it passes; otherwise it compiles the
named paths with ``python<major.minor>`` from PATH and fails on a compile error.

It detects compile-time errors only. Runtime behaviour differences between
Python versions are not caught here; required CI remains the merge gate.

    python3 scripts/check_ci_python.py --workflow .github/workflows/ci.yml --job validate \\
        --compile template/scripts --compile scripts --compile tests

Exit codes: 0 passed, 1 compilation failed on the CI version, 2 refused (the CI
version is unreadable or no interpreter of that version is available).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

SETUP_PYTHON = "actions/setup-python@"
VERSION = re.compile(r"3\.\d+")


class Refused(Exception):
    """An input the check needs is unreadable or unavailable; it never passes in its place."""


def ci_version(workflow: Path, job: str) -> str:
    """The ``major.minor`` the workflow job's single ``actions/setup-python`` step installs."""
    try:
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Refused(f"cannot read CI workflow {workflow}: {exc}") from exc
    jobs = document.get("jobs") if isinstance(document, dict) else None
    steps = jobs.get(job, {}).get("steps") if isinstance(jobs, dict) and isinstance(jobs.get(job), dict) else None
    if not isinstance(steps, list):
        raise Refused(f"CI workflow {workflow} has no job {job!r} with steps")
    setups = [step for step in steps
              if isinstance(step, dict) and str(step.get("uses", "")).startswith(SETUP_PYTHON)]
    if len(setups) != 1:
        raise Refused(f"CI workflow {workflow} job {job!r} has {len(setups)} {SETUP_PYTHON} steps; exactly one is required")
    options = setups[0].get("with")
    version = str(options.get("python-version", "")) if isinstance(options, dict) else ""
    if not VERSION.fullmatch(version):
        raise Refused(f"CI workflow {workflow} job {job!r} pins python-version {version or 'nothing'!r}; "
                      "expected major.minor such as 3.11")
    return version


def check(workflow: Path, job: str, paths: list[str], local: str) -> tuple[int, str]:
    """``(exit code, message)`` of the check for a local interpreter of version ``local``."""
    try:
        ci = ci_version(workflow, job)
    except Refused as exc:
        return 2, f"ci-python refused (local {local}, CI version unreadable): {exc}"
    if ci == local:
        return 0, f"ci-python: local {local} matches CI {ci}; the full check set runs on the CI version"
    interpreter = shutil.which(f"python{ci}")
    if interpreter is None:
        return 2, (f"ci-python refused: local {local}, CI {ci}: no python{ci} on PATH; "
                   f"install Python {ci} to validate against the CI version")
    probe = subprocess.run([interpreter, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                           capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    reported = probe.stdout.strip()
    if probe.returncode or reported != ci:
        return 2, (f"ci-python refused: local {local}, CI {ci}: {interpreter} reports "
                   f"{reported or 'no version'} (exit {probe.returncode})")
    compiled = subprocess.run([interpreter, "-m", "compileall", "-q", *paths],
                              capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    if compiled.returncode:
        output = (compiled.stdout + compiled.stderr).strip()[-4000:]
        return 1, f"ci-python failed: sources compile on local {local} but not on CI {ci}:\n{output}"
    return 0, (f"ci-python: local {local}, CI {ci}: {', '.join(paths)} compile on {interpreter}; "
               "only compile-time errors are checked on the CI version")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workflow", required=True, type=Path, help="CI workflow file that pins the Python version")
    parser.add_argument("--job", required=True, help="workflow job whose actions/setup-python step is read")
    parser.add_argument("--compile", dest="paths", action="append", required=True,
                        help="path to compile on the CI version (repeatable)")
    args = parser.parse_args()
    code, message = check(args.workflow, args.job, args.paths, "%d.%d" % sys.version_info[:2])
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
