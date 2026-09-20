"""Determine whether the current commit establishes publishable release intent.

Used by ``.github/workflows/publish-version.yml`` to decide, before creating
or confirming any tag/release, whether the current commit actually bumped
``VERSION`` relative to its parent -- as opposed to merely containing a
valid-looking ``VERSION`` value, which a fresh-history root/bootstrap commit
also does.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ReleaseIntentError(ValueError):
    """The current commit changed VERSION to a value that is not valid SemVer."""


@dataclass(frozen=True)
class ReleaseIntent:
    intent: bool
    reason: str
    version: str | None = None


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def _read_version(root: Path, ref: str) -> str | None:
    result = _run_git(root, "show", f"{ref}:VERSION")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def determine_release_intent(root: Path, *, new_ref: str = "HEAD") -> ReleaseIntent:
    """Whether ``new_ref`` actually establishes a publishable version bump.

    A root commit (no Git parent) never has release intent, regardless of
    what VERSION contains: a fresh-history bootstrap commit and a genuine
    first version bump are structurally identical by file content alone, so
    parentage is the only fact that can distinguish them.
    """
    parent = _run_git(root, "rev-parse", "-q", "--verify", f"{new_ref}^")
    if parent.returncode != 0:
        return ReleaseIntent(False, "repository-bootstrap-root-commit")
    new_version = _read_version(root, new_ref)
    if new_version is None:
        return ReleaseIntent(False, "version-file-missing")
    old_version = _read_version(root, f"{new_ref}^")
    if old_version == new_version:
        return ReleaseIntent(False, "version-unchanged", new_version)
    if not SEMVER_RE.fullmatch(new_version):
        raise ReleaseIntentError(f"VERSION must be SemVer X.Y.Z; got: {new_version!r}")
    return ReleaseIntent(True, "version-bump", new_version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    try:
        result = determine_release_intent(args.root, new_ref=args.ref)
    except ReleaseIntentError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"intent={'true' if result.intent else 'false'}")
    print(f"reason={result.reason}")
    print(f"version={result.version or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
