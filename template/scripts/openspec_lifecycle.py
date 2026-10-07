from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, harness_mode, lifecycle_mode, read_platform_config, run_git
try:
    from managed_task import ManagedTaskError, read_provenance, require_managed_checkout_identity, source_issue_for_provenance
except (ImportError, ModuleNotFoundError):  # Compatibility while old renders are upgraded.
    class ManagedTaskError(RuntimeError):
        pass

    def read_provenance(change: Path):
        return {}

    def source_issue_for_provenance(root: Path, change: Path, *, expected_source: str | None = None):
        return read_provenance(change).get("source_issue")

    def require_managed_checkout_identity(root: Path, *, expected_change: str | None = None, expected_source_issue: str | None = None):
        return None

try:
    from independent_review import require_review_evidence, review_is_required
except ModuleNotFoundError as exc:
    if exc.name != "independent_review":
        raise

    def review_is_required(root: Path, change: Path) -> bool:
        settings = read_platform_config(root).get("independent_review", {})
        return isinstance(settings, dict) and settings.get("enabled") is True and (change / ".managed-task.json").is_file()

    def require_review_evidence(root: Path, change: Path) -> None:
        if review_is_required(root, change):
            raise SystemExit(
                f"{change.name}: independent review is enabled but scripts/independent_review.py is missing; "
                "repair the incomplete platform update before archive readiness."
            )
try:
    from independent_review import ensure_review_evidence
except (ImportError, ModuleNotFoundError):  # Older renders validate only; they cannot launch a reviewer.
    def ensure_review_evidence(root: Path, change: Path, *, launcher: object = None) -> None:
        require_review_evidence(root, change)

# Mirrors upstream OpenSpec TASK_LINE_PATTERN (1.13.x dist/utils/task-progress.js): `-`, `*`, `+`,
# `N.` and `N)` markers; only `x`/`X` content is complete, any other checkbox content is open.
TASK_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s*\[(?:\s*([^\]\s]?)\s*\](?![(\[])|\s+\])")
VERIFY_MARKER = "OpenSpec-Verify: PASS"
VERIFY_METHOD_PREFIX = "Verification-Method:"
AUTOMATED_EVIDENCE_PREFIX = "Automated-Checks-Evidence:"
AUTOMATED_EVIDENCE_FILE = "automated-checks.json"
INDEPENDENT_REVIEW_EVIDENCE_PREFIX = "Independent-Review-Evidence:"
INDEPENDENT_REVIEW_EVIDENCE_FILE = "independent-review-request.json"
VERIFICATION_RECEIPT_CONTRACT = "docs/engineering/openspec-workflow.md#verify-archive-then-publish"


def active_changes(root: Path) -> list[Path]:
    changes = root / "openspec" / "changes"
    if not changes.exists():
        return []
    return sorted(path for path in changes.iterdir() if path.is_dir() and path.name != "archive")


def count_tasks(text: str) -> tuple[int, int]:
    total = incomplete = 0
    for line in text.splitlines():
        match = TASK_RE.match(line)
        if not match:
            continue
        total += 1
        if (match.group(1) or "").lower() != "x":
            incomplete += 1
    return total, incomplete


def task_state(change: Path) -> tuple[int, int]:
    tasks = change / "tasks.md"
    if not tasks.exists():
        return 0, 0
    return count_tasks(tasks.read_text(encoding="utf-8"))


def verification_passed(change: Path) -> bool:
    receipt = change / "verification.md"
    if not receipt.exists():
        return False
    lines = [line.strip() for line in receipt.read_text(encoding="utf-8").splitlines()]
    has_marker = VERIFY_MARKER in lines
    has_method = any(line.startswith(VERIFY_METHOD_PREFIX) and line.split(":", 1)[1].strip() for line in lines)
    return has_marker and has_method


def _without_clean_base_advance(root: Path, paths: list[str], actual_content: object, expected_content: object) -> list[str]:
    """Drop paths that arrived only through a clean merge of main.

    Content-aware receipts record the merge base the task diff was proven
    against.  When main advanced (ancestor -> descendant) without touching any
    task-owned path, the paths main changed are not task changes.  Any overlap
    with task-owned paths, or unknown/unrelated bases, keeps the raw range so
    the caller still fails closed.
    """
    if not isinstance(actual_content, dict) or not isinstance(expected_content, dict):
        return paths
    old_base, new_base = actual_content.get("base"), expected_content.get("base")
    recorded, current = actual_content.get("paths"), expected_content.get("paths")
    if not (isinstance(old_base, str) and isinstance(new_base, str) and isinstance(recorded, dict) and isinstance(current, dict)):
        return paths
    if old_base == new_base:
        return paths
    if run_git(["merge-base", "--is-ancestor", old_base, new_base], cwd=root, check=False).returncode:
        return paths
    advanced = run_git(["diff", "--name-only", old_base, new_base], cwd=root, check=False)
    if advanced.returncode:
        return paths
    base_paths = {line for line in advanced.stdout.splitlines() if line}
    if not base_paths.isdisjoint(set(recorded) | set(current)):
        return paths
    return [path for path in paths if path not in base_paths]


def evidence_matches_checkout(
    change: Path,
    root: Path,
    identity,
    actual: object,
) -> bool:
    """Accept exact validation identity, plus its own committed archive materialization.

    Archive must be committed before publication, which necessarily advances
    Git HEAD after validation.  That advancement is not an implementation
    change when it contains only this change's OpenSpec move/spec materialized
    by the archive helper.  Any other path, including every source/test path,
    remains a stale-evidence failure.
    """
    expected = identity.evidence_payload()
    if not isinstance(actual, dict):
        return False
    # New evidence is content-aware.  Keep exact SHA as provenance but accept
    # it across only a mechanically equal task-content proof.  Legacy receipts
    # retain the narrower archive-only transition below.
    # New selected-check receipts use the same lifecycle exclusions as review.
    # Keep checkout provenance stable while allowing evidence-only commits.
    try:
        evidence = json.loads((change / AUTOMATED_EVIDENCE_FILE).read_text())
    except (OSError, ValueError):
        evidence = {}
    recorded_gate = evidence.get("gate_task_content")
    if recorded_gate is not None:
        from task_content_identity import review_content_identity, equivalent_proofs

        stable_expected = {key: value for key, value in expected.items() if key not in {"head", "task_content"}}
        stable_actual = {key: value for key, value in actual.items() if key not in {"head", "task_content"}}
        return (stable_actual == stable_expected
                and equivalent_proofs(root, recorded_gate, review_content_identity(root, identity.change)))
    expected_content = expected.get("task_content")
    actual_content = actual.get("task_content") if isinstance(actual, dict) else None
    if isinstance(expected_content, dict) or isinstance(actual_content, dict):
        from task_content_identity import equivalent_proofs
        stable_expected = {key: value for key, value in expected.items() if key not in {"head", "task_content"}}
        stable_actual = {key: value for key, value in actual.items() if key not in {"head", "task_content"}}
        if (
            stable_actual == stable_expected
            and isinstance(expected_content, dict)
            and isinstance(actual_content, dict)
            and equivalent_proofs(root, actual_content, expected_content)
        ):
            return True
    if {key: value for key, value in actual.items() if key not in {"head", "task_content"}} != {
        key: value for key, value in expected.items() if key not in {"head", "task_content"}
    }:
        return False
    validated_head = actual.get("head")
    current_head = expected.get("head")
    if validated_head == current_head:
        return True
    if not isinstance(validated_head, str) or not isinstance(current_head, str):
        return False
    if run_git(["merge-base", "--is-ancestor", validated_head, current_head], cwd=root, check=False).returncode != 0:
        return False
    changed = run_git(["diff", "--name-only", f"{validated_head}..{current_head}"], cwd=root, check=False)
    if changed.returncode != 0:
        return False
    archive_prefix = change.relative_to(root).as_posix() + "/"
    provenance = read_provenance(change)
    canonical_change = provenance.get("change")
    if not isinstance(canonical_change, str):
        return False
    active_prefix = f"openspec/changes/{canonical_change}/"
    materialized_specs = {
        (Path("openspec/specs") / path.relative_to(change / "specs")).as_posix()
        for path in (change / "specs").glob("*/spec.md")
    }
    paths = [line for line in changed.stdout.splitlines() if line]
    paths = _without_clean_base_advance(root, paths, actual_content, expected_content)
    allowed = bool(paths) and all(
        path.startswith(archive_prefix) or path.startswith(active_prefix) or path in materialized_specs
        for path in paths
    )
    if not allowed:
        return False
    # A content-aware receipt can fall back only for the archive move. Every
    # archived file must be byte-for-byte equal to its validated active copy.
    if isinstance(actual_content, dict) or isinstance(expected_content, dict):
        archived = [path for path in paths if path.startswith(archive_prefix)]
        if not archived:
            return False
        for path in archived:
            source = active_prefix + path[len(archive_prefix):]
            old = run_git(["rev-parse", f"{validated_head}:{source}"], cwd=root, check=False)
            new = run_git(["rev-parse", f"{current_head}:{path}"], cwd=root, check=False)
            if source == active_prefix + AUTOMATED_EVIDENCE_FILE and not new.returncode:
                # The archive helper writes and may refresh this generated
                # receipt after the validated commit. Its contents are checked
                # separately by require_automated_evidence.
                continue
            if _is_review_evidence(path[len(archive_prefix):]) and not new.returncode:
                # Archive also produces independent-review evidence after the
                # validated commit; require_review_evidence binds it to the
                # task content separately.
                continue
            if old.returncode or new.returncode or old.stdout.strip() != new.stdout.strip():
                return False
    return True


REVIEW_EVIDENCE_FILES = ("independent-review-request.json", "independent-review-dispositions.json")
REVIEW_EVIDENCE_DIR = "independent-reviews/"


def _is_review_evidence(relative: str) -> bool:
    return relative in REVIEW_EVIDENCE_FILES or relative.startswith(REVIEW_EVIDENCE_DIR)


def require_automated_evidence(change: Path, *, root: Path | None = None) -> None:
    receipt = change / "verification.md"
    lines = [line.strip() for line in receipt.read_text(encoding="utf-8").splitlines()]
    expected_marker = f"{AUTOMATED_EVIDENCE_PREFIX} {AUTOMATED_EVIDENCE_FILE}"
    if expected_marker not in lines:
        raise SystemExit(
            f"{change.name}: platform-owned verification must cite '{expected_marker}' so the receipt cannot claim checks that did not run. "
            f"Add that exact line to verification.md; see {VERIFICATION_RECEIPT_CONTRACT}."
        )
    path = change / AUTOMATED_EVIDENCE_FILE
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{change.name}: missing readable automated check evidence: {path}") from exc
    selection = evidence.get("selection")
    executed = evidence.get("executed_commands")
    if not isinstance(selection, dict) or selection.get("state") != "ready":
        raise SystemExit(f"{change.name}: automated evidence does not show valid applicable platform coverage")
    if evidence.get("outcome") != "success" or not isinstance(executed, list):
        raise SystemExit(f"{change.name}: automated evidence does not show successful executed commands")
    if len(executed) != selection.get("command_count") or not executed:
        raise SystemExit(f"{change.name}: automated evidence command count does not match the selected platform coverage")
    if any(item.get("outcome") != "success" for item in executed if isinstance(item, dict)):
        raise SystemExit(f"{change.name}: automated evidence contains a failed command")
    if (change / ".managed-task.json").is_file():
        try:
            provenance = read_provenance(change)
            source_issue = source_issue_for_provenance((root or change.parents[2]).resolve(), change)
            canonical_change = provenance.get("change")
            if not isinstance(source_issue, str) or not isinstance(canonical_change, str):
                raise ManagedTaskError("managed-task provenance must identify source_issue and change for checkout evidence")
            identity = require_managed_checkout_identity(
                (root or change.parents[2]).resolve(),
                expected_change=canonical_change,
                expected_source_issue=source_issue,
            )
        except ManagedTaskError as exc:
            raise SystemExit(f"{change.name}: managed checkout identity cannot accept automated evidence: {exc}") from exc
        actual = evidence.get("managed_checkout")
        if identity is None or not evidence_matches_checkout(change, (root or change.parents[2]).resolve(), identity, actual):
            raise SystemExit(
                f"{change.name}: automated evidence checkout identity does not match this managed task; "
                "rerun validation from the exact registered task checkout. Only the same change's committed OpenSpec archive materialization may follow a validated HEAD."
            )


def require_independent_review_receipt(change: Path) -> None:
    """Keep enabled independent-review evidence visible from verification.md."""
    root = change.parents[2]
    if not review_is_required(root, change):
        return
    expected = f"{INDEPENDENT_REVIEW_EVIDENCE_PREFIX} {INDEPENDENT_REVIEW_EVIDENCE_FILE}"
    lines = [line.strip() for line in (change / "verification.md").read_text(encoding="utf-8").splitlines()]
    if expected not in lines:
        raise SystemExit(
            f"{change.name}: independent review must cite '{expected}' in verification.md so the PASS receipt names its evidence."
        )


def require_publication_review_evidence(change: Path, *, root: Path | None = None) -> None:
    """Finish gate: required review evidence must match the current task content."""
    work = (root or change.parents[2]).resolve()
    if not review_is_required(work, change):
        return
    try:
        require_review_evidence(work, change)
    except SystemExit as exc:
        raise SystemExit(
            f"Publication refused before any remote mutation: {exc}\n"
            "Rerun the independent review for the current candidate, commit its evidence, then rerun finish."
        ) from exc


STAGE_CANDIDATE = "candidate"
STAGE_INTEGRATION = "integration"

# Reserved context variable: set only in the environment of the single validation
# subprocess that ``archive`` launches, so hygiene exempts exactly the archive target.
ARCHIVE_TARGET_ENV = "DEV_PLATFORM_ARCHIVE_TARGET"
ARCHIVE_ROOT_ENV = "DEV_PLATFORM_ARCHIVE_ROOT"
ARCHIVE_TARGET_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def require_archive_target(root: Path, target: str, *, source: str) -> None:
    """Fail closed unless ``target`` names exactly one existing completed active change."""
    if not ARCHIVE_TARGET_RE.fullmatch(target) or target == "archive":
        raise SystemExit(f"{source}: archive target {target!r} is not a valid OpenSpec change name")
    matches = [path for path in active_changes(root) if path.name == target]
    if len(matches) != 1:
        raise SystemExit(f"{source}: archive target {target!r} is not an existing active OpenSpec change")
    if target not in completed_active_changes(root):
        raise SystemExit(f"{source}: archive target {target!r} is not a completed active change (no tasks or tasks incomplete)")


def archive_target_environment(root: Path, target: str) -> dict[str, str]:
    """Validated environment for the one validation subprocess of an archive invocation."""
    require_archive_target(root, target, source="archive")
    env = dict(os.environ)
    env[ARCHIVE_TARGET_ENV] = target
    env[ARCHIVE_ROOT_ENV] = os.path.realpath(root)
    return env


def completed_active_changes(root: Path) -> list[str]:
    stale: list[str] = []
    for change in active_changes(root):
        total, incomplete = task_state(change)
        if total > 0 and incomplete == 0:
            stale.append(change.name)
    return stale


def completed_active_changes_at(root: Path, ref: str) -> list[str]:
    """Completed-but-active changes in the committed tree at ``ref`` (no checkout needed)."""
    listed = run_git(["ls-tree", "--name-only", ref, "openspec/changes/"], cwd=root, check=False)
    if listed.returncode:
        raise SystemExit(f"cannot list OpenSpec changes at {ref}: {listed.stderr.strip()}")
    stale: list[str] = []
    for entry in sorted(listed.stdout.splitlines()):
        name = entry.rsplit("/", 1)[-1]
        if name == "archive":
            continue
        tasks = run_git(["show", f"{ref}:{entry}/tasks.md"], cwd=root, check=False)
        if tasks.returncode:
            continue
        total, incomplete = count_tasks(tasks.stdout)
        if total > 0 and incomplete == 0:
            stale.append(name)
    return stale


def _candidate_context(root: Path) -> bool:
    """Whether this checkout is a source-repository work branch or PR, never main itself."""
    config = read_platform_config(root)
    if config.get("platform_version") != "source":
        return False
    main = str(config.get("main_branch", "main"))
    ref = os.environ.get("GITHUB_REF", "")
    if ref:
        return ref.startswith("refs/pull/") or (ref.startswith("refs/heads/") and ref != f"refs/heads/{main}")
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root, check=False).stdout.strip()
    return branch not in {"", "HEAD", main}


def check_hygiene(root: Path, stage: str | None = None) -> int:
    """Block completed-but-active changes at the stage where archive is required.

    ``integration`` (publication by a non-coordinator flow, integration admission,
    merge, main) is strict. ``candidate`` allows a completed managed change that a
    coordinator-managed PR carries until review and repair finish. With no stage
    the context decides: only a source-repository work branch or PR is a candidate.
    """
    if stage is None:
        stage = STAGE_CANDIDATE if _candidate_context(root) else STAGE_INTEGRATION
    stale = completed_active_changes(root)
    archive_target = os.environ.get(ARCHIVE_TARGET_ENV)
    archive_root = os.environ.get(ARCHIVE_ROOT_ENV)
    if (archive_target is None) != (archive_root is None):
        raise SystemExit(
            f"hygiene: malformed archive context: {ARCHIVE_TARGET_ENV} and {ARCHIVE_ROOT_ENV} must be set together"
        )
    for variable, value in ((ARCHIVE_TARGET_ENV, archive_target), (ARCHIVE_ROOT_ENV, archive_root)):
        if value is not None and not value.strip():
            raise SystemExit(f"hygiene: malformed archive context: {variable} is empty")
    if archive_root is not None and not os.path.isabs(archive_root):
        raise SystemExit(f"hygiene: malformed archive context: {ARCHIVE_ROOT_ENV} must be an absolute path")
    # A context issued for another checkout (e.g. a test tree run under archive) is not ours:
    # hygiene then runs as the ordinary check, with no exemption and no error.
    if archive_target is not None and os.path.realpath(archive_root) == os.path.realpath(root):
        require_archive_target(root, archive_target, source=f"hygiene ({ARCHIVE_TARGET_ENV})")
        stale = [name for name in stale if name != archive_target]
    if stage == STAGE_CANDIDATE:
        stale = [name for name in stale if not (root / "openspec" / "changes" / name / ".managed-task.json").is_file()]
    if not stale:
        print("OpenSpec lifecycle hygiene: OK")
        return 0
    print("OpenSpec lifecycle hygiene: BLOCKED")
    for name in stale:
        print(f"- {name}: all tasks are complete but the change is still active")
    print("Run /opsx:verify when available (or the documented equivalent semantic review), resolve findings, record the PASS receipt and method, then archive through scripts/openspec_lifecycle.py.")
    return 1


def require_ready(change: Path, *, platform_owned: bool = False, reviewed_composition: bool = False) -> None:
    if not change.exists() or not change.is_dir():
        raise SystemExit(f"Active OpenSpec change not found: {change.name}")
    total, incomplete = task_state(change)
    if total == 0:
        raise SystemExit(f"{change.name}: tasks.md has no task checkboxes; refusing automatic archive")
    if incomplete:
        raise SystemExit(f"{change.name}: {incomplete} of {total} task(s) remain incomplete")
    if not verification_passed(change):
        raise SystemExit(
            f"{change.name}: missing successful semantic verification receipt. "
            f"Run /opsx:verify when available (or an equivalent documented OpenSpec verification), resolve material findings, "
            f"then record '{VERIFY_MARKER}' and a '{VERIFY_METHOD_PREFIX} <method>' line in verification.md."
        )
    if not reviewed_composition:
        require_review_evidence(change.parents[2], change)
    require_independent_review_receipt(change)
    if platform_owned:
        require_automated_evidence(change)


def require_managed_routing_evidence(change: Path) -> None:
    """Block a managed archive before mutation when exact route evidence is absent.

    The active change supplies the exact identity at this structural boundary;
    ``model_routing`` may then validate its durable integration-owned record.
    Unmanaged OpenSpec changes keep their existing lifecycle behavior.
    """
    provenance = change / ".managed-task.json"
    if not provenance.is_file():
        return
    try:
        payload = json.loads(provenance.read_text(encoding="utf-8"))
        source_issue = source_issue_for_provenance(change.parents[2], change)
        managed_change = payload["change"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{change.name}: routing archive gate cannot read exact managed-task provenance") from exc
    if not isinstance(source_issue, str) or not source_issue or managed_change != change.name:
        raise SystemExit(f"{change.name}: routing archive gate found invalid managed-task provenance")
    try:
        import model_routing
        model_routing.require_routing_gate(change.parents[2], source_issue, managed_change)
    except ModuleNotFoundError as exc:
        if exc.name != "model_routing":
            raise
        raise SystemExit(
            f"{change.name}: routing archive gate requires scripts/model_routing.py; repair the incomplete platform lifecycle before archive"
        ) from exc
    except Exception as exc:
        raise SystemExit(
            f"{change.name}: routing archive gate blocked: {exc}. "
            "Record the required route and real execution/retention outcome before implementation and archive."
        ) from exc


def require_static_archive_readiness(change: Path, *, platform_owned: bool = False, review: bool = True, routing: bool = True) -> None:
    """Check deterministic archive prerequisites before checks mutate evidence.

    ``review=False`` lets archive defer the (possibly launching) independent
    review until after every cheap deterministic prerequisite has passed.
    """
    if not change.exists() or not change.is_dir():
        raise SystemExit(f"Active OpenSpec change not found: {change.name}")
    total, incomplete = task_state(change)
    if total == 0:
        raise SystemExit(f"{change.name}: tasks.md has no task checkboxes; refusing automatic archive")
    if incomplete:
        raise SystemExit(f"{change.name}: {incomplete} of {total} task(s) remain incomplete")
    if not verification_passed(change):
        raise SystemExit(
            f"{change.name}: missing successful semantic verification receipt. "
            f"Run /opsx:verify when available (or an equivalent documented OpenSpec verification), resolve material findings, "
            f"then record '{VERIFY_MARKER}' and a '{VERIFY_METHOD_PREFIX} <method>' line in verification.md."
        )
    require_independent_review_receipt(change)
    if review:
        require_review_evidence(change.parents[2], change)
    if platform_owned and routing:
        require_managed_routing_evidence(change)
    if platform_owned:
        expected = f"{AUTOMATED_EVIDENCE_PREFIX} {AUTOMATED_EVIDENCE_FILE}"
        lines = [line.strip() for line in (change / "verification.md").read_text(encoding="utf-8").splitlines()]
        if expected not in lines:
            raise SystemExit(
                f"{change.name}: platform-owned verification must cite '{expected}' before archive can run checks. "
                f"Add that exact line to verification.md; see {VERIFICATION_RECEIPT_CONTRACT}."
            )


def require_applicable_committed_diff(root: Path) -> None:
    """Reject uncommitted-only packages before selecting checks or writing evidence."""
    result = run_git(["diff", "--quiet", "origin/main...HEAD"], cwd=root, check=False)
    if result.returncode == 0:
        raise SystemExit(
            "OpenSpec archive requires an applicable committed diff against origin/main; "
            "uncommitted or untracked-only package state is not archiveable."
        )
    if result.returncode != 1:
        raise SystemExit("OpenSpec archive could not determine committed diff against origin/main.")


def run_checked(command: list[str], root: Path, *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def archive_change(root: Path, name: str, *, finalize: bool = False) -> int:
    """Archive a verified change.

    ``finalize`` is the coordinator's post-review archive of a disposable candidate
    checkout: review and selected-check evidence are reused (never launched or rerun),
    and the local task-checkout identity gates do not apply because the trusted
    coordinator already proved the content-bound gates before invoking it.
    """
    # Fail closed on a nonexistent, malformed or not-completed target before any state changes.
    require_archive_target(root, name, source="archive")
    # Cheap privacy gate before review, checks, evidence writes or OpenSpec mutation.
    import private_lineage
    try:
        private_lineage.require_clean_candidate(root)
    except private_lineage.PrivateLineageError as exc:
        raise SystemExit(f"{name}: archive blocked before review and validation: {exc}") from exc
    change = root / "openspec" / "changes" / name
    platform_owned = harness_mode(read_platform_config(root)) == "platform"
    if platform_owned and not finalize and (change / ".managed-task.json").is_file():
        try:
            source_issue = source_issue_for_provenance(root, change)
            if not isinstance(source_issue, str):
                raise ManagedTaskError("managed-task provenance must identify source_issue for checkout evidence")
            require_managed_checkout_identity(
                root,
                expected_change=name,
                expected_source_issue=source_issue,
            )
        except ManagedTaskError as exc:
            raise SystemExit(f"{name}: managed checkout identity gate blocked archive before validation: {exc}") from exc
    require_static_archive_readiness(change, platform_owned=platform_owned, review=False, routing=not finalize)
    if platform_owned and not finalize:
        require_applicable_committed_diff(root)
    composition = os.environ.get("DEV_PLATFORM_COMPOSITION_FINALIZATION") if finalize else None
    if composition:
        from requirement_composition import require_archive_evidence
        require_archive_evidence(root, name, composition)
    elif finalize:
        require_review_evidence(root, change)
    else:
        # Required independent review runs after the cheap deterministic gates and
        # before expensive validation: a missing or stale review is launched now,
        # and blocking findings stop archive with exact next commands.
        if lifecycle_mode(read_platform_config(root)) == "coordinator":
            from pr_review_gate import managed_candidate

            coordinator_managed = managed_candidate(root)
        else:
            coordinator_managed = False
        if coordinator_managed:
            require_review_evidence(root, change)
        else:
            ensure_review_evidence(root, change)
        if platform_owned and coordinator_managed:
            # Validate content-bound selected checks; never rerun unchanged evidence.
            require_automated_evidence(change, root=root)
        elif platform_owned:
            evidence = change / AUTOMATED_EVIDENCE_FILE
            run_checked(
                ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute", "--evidence", str(evidence)],
                root,
                env=archive_target_environment(root, name),
            )
    require_ready(change, platform_owned=platform_owned and not finalize, reviewed_composition=bool(composition))
    executable = shutil.which("openspec")
    if not executable:
        raise SystemExit("OpenSpec CLI is required to archive a verified change")
    run_checked([executable, "validate", name, "--strict", "--no-interactive"], root)
    run_checked([executable, "archive", name, "--yes"], root)
    run_checked([executable, "validate", "--all", "--strict", "--no-interactive"], root)
    print(f"Archived verified OpenSpec change: {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce the OpenSpec verify/archive completion contract.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Fail if a completed change is still active where archive is required.")
    check.add_argument("--stage", choices=(STAGE_CANDIDATE, STAGE_INTEGRATION),
                       help="integration is strict; candidate allows a completed managed change before finalization")
    archive = sub.add_parser("archive", help="Archive a completed, semantically verified change.")
    archive.add_argument("change")
    archive.add_argument("--finalize", action="store_true",
                         help="coordinator finalization of a reviewed candidate: reuse review and check evidence")
    args = parser.parse_args()
    root = current_worktree_root()
    if args.command == "check":
        return check_hygiene(root, args.stage)
    return archive_change(root, args.change, finalize=args.finalize)


if __name__ == "__main__":
    raise SystemExit(main())
