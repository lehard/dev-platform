"""Extract a real public snapshot and prove the result is developable.

This is the deterministic snapshot-smoke path required by this change's
tasks.md #2: the current-tree audit in `scripts/public_distribution.py`
proves the *source* candidate set is clean, but only extracting the actual
tarball into a clean directory and running verification from inside it
proves the *packaged* result is a self-contained, developable, testable
canonical source checkout -- not just a source tree that happens to pass
while still sitting next to the original checkout's untracked state.

Not a `unittest` module (no `test_` prefix): like `upgrade_smoke.py` and
`rollout_recopy_smoke.py`, it is invoked directly as its own CI step because
it extracts and exercises a real snapshot end-to-end rather than asserting
against synthetic fixtures.
"""
from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import public_distribution  # noqa: E402

# Bounded verification run from inside the extracted snapshot: proves the
# packaged tree can compile, discover, and pass its own required test/spec
# gates with no dependency on the original checkout's untracked/local state.
EXTRACTED_CHECK_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("python3", "-m", "compileall", "-q", "template/scripts", "scripts"),
    ("python3", "scripts/run_test_groups.py", "--all"),
    ("python3", "template/scripts/openspec_lifecycle.py", "check"),
)

# Paths whose presence in the extracted snapshot root is required evidence
# that the packaging boundary retained what this change's proposal requires:
# required tests, accepted specs, current OpenSpec lifecycle configuration,
# release/CI machinery, and the template.
REQUIRED_TOP_LEVEL_PATHS = (
    "README.md",
    "tests",
    "openspec/specs",
    "openspec/config.yaml",
    "template",
    "scripts",
    ".github/workflows",
)


def run(command: tuple[str, ...], cwd: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(f"snapshot smoke command failed (exit {result.returncode}): {' '.join(command)}")


def establish_fresh_history(extracted: Path) -> None:
    """Give the extracted tree its own first-commit Git identity.

    The platform lifecycle scripts (`current_worktree_root`, etc.) require a
    real Git worktree; `.git` is never part of the packaged candidate set
    (see `scripts/public_distribution.py` `EXCLUDED_PARTS`), so a snapshot
    smoke reproduces exactly what a real cutover does per docs/public-cutover.md:
    "Establish the fresh canonical history" -- a single commit over the
    extracted tree, nothing more.
    """
    for command in (
        ("git", "init", "-q"),
        ("git", "config", "user.email", "snapshot-smoke@example.invalid"),
        ("git", "config", "user.name", "Snapshot Smoke"),
        ("git", "add", "-A"),
        ("git", "commit", "-q", "-m", "snapshot smoke: fresh canonical history"),
    ):
        run(command, extracted)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dev-platform-snapshot-smoke-") as tmp:
        tmp_path = Path(tmp)
        snapshot_path = tmp_path / "dev-platform-snapshot.tar"
        extracted = tmp_path / "extracted"
        extracted.mkdir()

        result = public_distribution.snapshot(ROOT, snapshot_path)
        digest = result["sha256"]
        source_revision = result["audit"]["source_revision"]
        print(
            f"Snapshot built: {result['files']} files, sha256={digest}, "
            f"source_revision={source_revision}",
            flush=True,
        )

        with tarfile.open(snapshot_path) as archive:
            archive.extractall(extracted, filter="data")

        missing_top_level = [
            relative for relative in REQUIRED_TOP_LEVEL_PATHS if not (extracted / relative).exists()
        ]
        if missing_top_level:
            raise SystemExit(
                "extracted snapshot is missing required top-level paths: " + ", ".join(missing_top_level)
            )

        missing_referenced = public_distribution.missing_required_paths(
            extracted, public_distribution.public_files(extracted)
        )
        if missing_referenced:
            raise SystemExit(
                "extracted snapshot's own README/CI reference paths it does not contain: "
                + ", ".join(missing_referenced)
            )

        establish_fresh_history(extracted)

        for command in EXTRACTED_CHECK_COMMANDS:
            run(command, extracted)

        print(
            "Snapshot smoke passed: extracted tree is self-contained, path-complete, "
            f"and developable from source_revision={source_revision}, "
            f"candidate_sha256={digest}.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
