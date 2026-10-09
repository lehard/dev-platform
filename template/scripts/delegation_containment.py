#!/usr/bin/env python3
"""Detect whether a delegated write-capable subagent stayed within its assigned worktree.

See openspec/specs/platform-delegation/spec.md for the contract. This module only
detects and reports; it never stashes, resets, or deletes anything in the
integration copy, since changed paths there may be another agent's legitimate
concurrent work.

The snapshot is content-aware: a dirty/untracked path is fingerprinted by its
actual index blob (when staged) and worktree bytes/symlink target/executable
bit, not merely by its two-character porcelain status code. This lets the
post-check tell "still the same pre-existing dirty state" apart from "someone
changed the contents of that already-dirty path while delegation was running",
even when the status code did not change. Only paths already reported dirty or
untracked by `git status` are fingerprinted, so this never hashes the whole
repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - POSIX-only locking, same posture as the other platform logs.
    fcntl = None  # type: ignore[assignment]


class ContainmentError(RuntimeError):
    """A user-facing containment safety error."""


@dataclass(frozen=True)
class PathState:
    status: str  # two-character porcelain status code (XY)
    fingerprint: str  # opaque content-aware fingerprint; equal iff relevant state is equal
    orig_path: str | None = None  # rename/copy source, when applicable


@dataclass(frozen=True)
class GitSnapshot:
    head: str
    paths: dict[str, PathState]


@dataclass(frozen=True)
class ContainmentResult:
    violated: bool
    new_changes: tuple[str, ...]
    pre_existing_changes: tuple[str, ...]
    disappeared_changes: tuple[str, ...]
    head_moved: bool


def run_git(cwd: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, check=False)
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ContainmentError(f"git {' '.join(arguments)} failed: {detail}")
    return completed


def resolve_assigned_worktree(integration_root: Path, assigned_worktree: str | Path) -> Path:
    """Validate assigned_worktree is an absolute, registered worktree distinct from integration_root."""
    raw = Path(assigned_worktree)
    if not raw.is_absolute():
        raise ContainmentError(f"assigned_worktree must be an absolute path, got {raw}")
    resolved = raw.expanduser().resolve()
    integration_resolved = integration_root.resolve()
    if resolved == integration_resolved:
        raise ContainmentError("assigned_worktree must not be the integration copy itself")
    listing = run_git(integration_root, "worktree", "list", "--porcelain")
    registered = {
        Path(line[len("worktree ") :]).resolve()
        for line in listing.stdout.splitlines()
        if line.startswith("worktree ")
    }
    if resolved not in registered:
        raise ContainmentError(f"assigned_worktree {resolved} is not a registered git worktree of {integration_root}")
    return resolved


def _parse_porcelain_z(output: str) -> list[tuple[str, str, str | None]]:
    """Parse `git status --porcelain=v1 -z` output into (status, path, orig_path) triples.

    The -z form is NUL-delimited and leaves paths unquoted/unescaped, which avoids the
    whitespace/quoting ambiguity of the newline-delimited default format. Rename/copy
    entries carry an extra NUL-terminated original-path field immediately after the path.
    """
    tokens = output.split("\0")
    entries: list[tuple[str, str, str | None]] = []
    index = 0
    total = len(tokens)
    while index < total:
        token = tokens[index]
        if token == "":
            index += 1
            continue
        status = token[:2]
        path = token[3:]
        index += 1
        orig_path: str | None = None
        if status[0] in ("R", "C") and index < total:
            orig_path = tokens[index]
            index += 1
        entries.append((status, path, orig_path))
    return entries


def _worktree_fingerprint(full_path: Path) -> str:
    """Content-aware fingerprint of a path's current worktree state.

    Read-only. Distinguishes absent/regular-file-content/executable-bit/symlink-target.
    Raises ContainmentError if the path exists but cannot be inspected consistently.
    """
    try:
        stat_result = full_path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        raise ContainmentError(f"cannot inspect worktree path {full_path}: {exc}") from exc

    mode = stat_result.st_mode
    if stat.S_ISLNK(mode):
        try:
            target = os.readlink(full_path)
        except OSError as exc:
            raise ContainmentError(f"cannot read symlink {full_path}: {exc}") from exc
        return f"symlink:{target}"
    if stat.S_ISREG(mode):
        executable = "x" if mode & stat.S_IXUSR else "-"
        try:
            digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ContainmentError(f"cannot read worktree path {full_path}: {exc}") from exc
        return f"file:{executable}:{digest}"
    raise ContainmentError(f"unsupported filesystem entry type for containment snapshot: {full_path}")


def _index_fingerprints(integration_root: Path, paths: list[str]) -> dict[str, str]:
    """Batched `git ls-files -s` blob/mode fingerprint for paths with a staged change."""
    if not paths:
        return {}
    result = run_git(integration_root, "ls-files", "-s", "-z", "--", *paths)
    fingerprints: dict[str, str] = {}
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        meta, _, path = entry.partition("\t")
        pieces = meta.split(" ")
        if len(pieces) < 2:
            raise ContainmentError(f"unexpected `git ls-files -s` output for {path!r}: {meta!r}")
        mode, blob = pieces[0], pieces[1]
        fingerprints[path] = f"index:{mode}:{blob}"
    return fingerprints


def snapshot(integration_root: Path) -> GitSnapshot:
    """Capture integration_root's committed HEAD and a content-aware dirty/untracked state map.

    Raises ContainmentError if the snapshot itself cannot be taken; callers must
    treat that as a containment-check failure, not as "no violation."
    """
    head = run_git(integration_root, "rev-parse", "HEAD").stdout.strip()
    status_output = run_git(
        integration_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).stdout
    raw_entries = _parse_porcelain_z(status_output)

    needs_index_fingerprint = [path for status, path, _orig in raw_entries if status[0] not in (" ", "?")]
    index_fingerprints = _index_fingerprints(integration_root, needs_index_fingerprint)

    paths: dict[str, PathState] = {}
    for status, path, orig_path in raw_entries:
        worktree_fp = _worktree_fingerprint(integration_root / path)
        index_fp = index_fingerprints.get(path, "index:none")
        paths[path] = PathState(status=status, fingerprint=f"{index_fp}|{worktree_fp}", orig_path=orig_path)
    return GitSnapshot(head=head, paths=paths)


def check_containment(before: GitSnapshot, after: GitSnapshot) -> ContainmentResult:
    """Compare two content-aware snapshots of the same integration_root and classify the diff.

    A path present in both snapshots is pre-existing-unchanged only when both its status
    code and its content-aware fingerprint are identical -- not merely when the status code
    matches, since the same status code can persist across a real content mutation (for
    example a tracked file staying " M" while its bytes change). A path that disappears
    between snapshots (its dirty/untracked state resolved somehow during delegation) is
    reported rather than silently dropped, since attribution cannot be proven from
    snapshots alone.
    """
    new_changes: list[str] = []
    pre_existing: list[str] = []
    for path, after_state in after.paths.items():
        before_state = before.paths.get(path)
        if (
            before_state is None
            or before_state.status != after_state.status
            or before_state.fingerprint != after_state.fingerprint
        ):
            new_changes.append(path)
        else:
            pre_existing.append(path)
    disappeared = [path for path in before.paths if path not in after.paths]
    head_moved = before.head != after.head
    violated = bool(new_changes) or bool(disappeared) or head_moved
    return ContainmentResult(
        violated=violated,
        new_changes=tuple(sorted(new_changes)),
        pre_existing_changes=tuple(sorted(pre_existing)),
        disappeared_changes=tuple(sorted(disappeared)),
        head_moved=head_moved,
    )


def verify_remote_fast_forward(integration_root: Path, before_head: str, after_head: str) -> bool:
    """Whether `after_head` is a verified concurrent fast-forward of `before_head`.

    Proves two facts, both required: `after_head` is a fast-forward descendant
    of `before_head`, and `after_head` exactly equals this checkout's own
    already-recorded remote-tracking ref for the configured base branch
    (`refs/remotes/origin/<main_branch>`) -- never a fresh network round-trip,
    since this must stay a read of local state the checkout already has. Fails
    closed (returns False) on any git error, missing config, or mismatch; a
    verification failure is never treated as proof.
    """
    try:
        from _platform_common import read_platform_config  # local import: avoid a hard dependency for callers that never need config.

        config = read_platform_config(integration_root)
    except Exception:
        return False
    main_branch = str(config.get("main_branch") or "main")
    ancestry = run_git(integration_root, "merge-base", "--is-ancestor", before_head, after_head, check=False)
    if ancestry.returncode != 0:
        return False
    remote_ref = run_git(integration_root, "rev-parse", f"refs/remotes/origin/{main_branch}", check=False)
    if remote_ref.returncode != 0:
        return False
    return remote_ref.stdout.strip() == after_head


def verify_historical_external_advance(
    integration_root: Path, before_head: str, after_head: str, *, not_before: str, not_after: str
) -> bool:
    """Whether `after_head` is provably this checkout's own remote-tracking main at
    some point during the caller-supplied `[not_before, not_after]` window.

    This is the historical-only counterpart to `verify_remote_fast_forward`, used
    solely by `model_routing.recover_external_advance`'s recovery path -- never by
    the live containment postcheck, and it never calls `verify_remote_fast_forward`
    itself. By the time recovery runs, `refs/remotes/origin/<main_branch>` has
    legitimately kept advancing past the historically observed `after_head`
    (including through unrelated later merges), so requiring an exact match against
    the *current* ref -- as the live check correctly does -- would make every real
    historical incident permanently unrecoverable.

    Proves, all independently:
      1. `before_head` is a fast-forward ancestor of `after_head`.
      2. `after_head` is an ancestor of (or equal to) the checkout's *current*
         `refs/remotes/origin/<main_branch>` -- ruling out an orphan/reset commit
         that never became real, accepted history.
      3. `refs/remotes/origin/<main_branch>`'s own local reflog records an entry
         whose value is exactly `after_head`, at a timestamp inside the inclusive
         `[not_before, not_after]` window.

    Ancestry to current main (fact 2) alone is NOT sufficient historical provenance:
    it proves `after_head` is *somewhere* in accepted history, not that it was ever
    actually this checkout's own recorded remote-tracking main at the time of the
    incident being recovered -- a commit that later lands on main through any
    unrelated path would otherwise satisfy ancestry without ever having been the
    observed external advance. Only the reflog binding (fact 3) supplies that missing
    temporal, ref-identity-specific fact. `not_before`/`not_after` MUST come from the
    route's own durably recorded execution timing -- never a hardcoded external fact
    such as a specific PR or commit timestamp -- or the caller has nothing legitimate
    to bind against.

    Fails closed (returns False, never raises) on any git error, missing/unparseable
    platform config, an unparseable `not_before`/`not_after`, an expired/missing
    reflog, or no matching entry inside the window.
    """
    try:
        from _platform_common import read_platform_config, remote_ref  # local import: same reasoning as verify_remote_fast_forward.

        config = read_platform_config(integration_root)
    except Exception:
        return False
    main_branch = str(config.get("main_branch") or "main")

    try:
        lower = datetime.fromisoformat(not_before)
        upper = datetime.fromisoformat(not_after)

        forward = run_git(integration_root, "merge-base", "--is-ancestor", before_head, after_head, check=False)
        if forward.returncode != 0:
            return False

        ref = remote_ref("origin", main_branch)
        contained = run_git(integration_root, "merge-base", "--is-ancestor", after_head, ref, check=False)
        if contained.returncode != 0:
            return False

        reflog = run_git(integration_root, "log", "-g", "--format=%H %gd", "--date=iso-strict", ref, check=False)
        if reflog.returncode != 0:
            return False

        for line in reflog.stdout.splitlines():
            if not line.strip():
                continue
            sha, _, rest = line.partition(" ")
            if sha != after_head:
                continue
            match = re.search(r"@\{([^}]+)\}", rest)
            if not match:
                continue
            when = datetime.fromisoformat(match.group(1))
            if lower <= when <= upper:
                return True
        return False
    except Exception:
        return False


# --- Integration-advance receipts and the shared head-move classifier ----------

INTEGRATION_ADVANCE_LOG = Path(".claude") / "integration-advances.jsonl"
# Same string value as `delegated_write_guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE`;
# a test pins the equality because the guard imports this module, not the reverse.
CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE = "verified_external_advance"
TIER_HARD = "hard"
TIER_DETECTION_ONLY = "detection-only"
_RECEIPT_FIELDS = ("before", "after", "remote", "remote_main", "actor_worktree", "tool", "pid", "at")


def integration_advance_log(integration_root: Path) -> Path:
    return integration_root / INTEGRATION_ADVANCE_LOG


def _configured_main_branch(integration_root: Path) -> str:
    from _platform_common import read_platform_config  # local import: keep this module importable without platform config.

    branch = read_platform_config(integration_root).get("main_branch")
    if not isinstance(branch, str) or not branch:
        raise ContainmentError(f"platform config for {integration_root} does not name main_branch; cannot record an integration advance")
    return branch


def record_integration_advance(
    integration_root: Path, before: str, after: str, *, tool: str, actor_worktree: Path, remote: str
) -> dict[str, Any]:
    """Append a receipt for a fast-forward of the integration checkout's main branch.

    Call only after the fast-forward succeeded, from the code path that performed
    it. The receipt records the local remote-tracking main as read right now, so a
    later detection-only classification can prove the move landed on the
    already-recorded remote main and who performed it. Raises `ContainmentError`
    on any failure: the advance already happened, so a missing receipt must be
    loud (a delegation overlapping it stays fail-closed) rather than silently
    unclassifiable.
    """
    if not before or not after:
        raise ContainmentError("integration advance receipt requires non-empty before and after heads")
    if before == after:
        raise ContainmentError("integration advance receipt requires a head that actually moved")
    from _platform_common import cooperative_umask, ensure_shared_path  # local import, see above.

    branch = _configured_main_branch(integration_root)
    remote_main = run_git(integration_root, "rev-parse", f"refs/remotes/{remote}/{branch}").stdout.strip()
    receipt = {
        "before": before,
        "after": after,
        "remote": remote,
        "remote_main": remote_main,
        **({"origin_main": remote_main} if remote == "origin" else {}),
        "actor_worktree": str(Path(actor_worktree).resolve()),
        "tool": tool,
        "pid": os.getpid(),
        "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    log = integration_advance_log(integration_root)
    lock = log.with_suffix(log.suffix + ".lock")
    try:
        cooperative_umask()
        log.parent.mkdir(parents=True, exist_ok=True)
        ensure_shared_path(log.parent)
        with lock.open("a+", encoding="utf-8") as lock_file:
            ensure_shared_path(lock)
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(receipt, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                ensure_shared_path(log)
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise ContainmentError(
            f"integration advance {before[:12]}..{after[:12]} happened but its receipt could not be written to {log}: {exc}"
        ) from exc
    return receipt


def _parse_receipt_time(value: Any, where: str) -> datetime:
    if not isinstance(value, str):
        raise ContainmentError(f"{where}: timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ContainmentError(f"{where}: unparseable timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ContainmentError(f"{where}: timestamp {value!r} has no timezone")
    return parsed


def require_own_fast_forward(integration_root: Path, branch: str, before: str, after: str, source: str) -> None:
    """Prove from ``branch``'s reflog that this caller's ``git merge --ff-only <source>`` moved it ``before`` -> ``after``.

    A concurrent writer that advanced ``branch`` between the caller's head read and its merge leaves a
    different newest entry (an up-to-date merge writes none), so the advance cannot be misattributed.
    """
    lines = run_git(integration_root, "log", "-g", "-2", "--format=%H%x00%gs", f"refs/heads/{branch}").stdout.splitlines()
    entries = [line.split("\x00", 1) for line in lines]
    if len(entries) != 2 or entries[0] != [after, f"merge {source}: Fast-forward"] or entries[1][0] != before:
        raise ContainmentError(
            f"{branch} reflog does not show this caller's fast-forward {before[:12]}..{after[:12]} from {source}; "
            "integration moved concurrently, so no integration advance receipt is written"
        )


def read_integration_advances(integration_root: Path) -> list[dict[str, Any]]:
    """Read every receipt, strictly. An absent log is an empty list; any malformed line raises."""
    log = integration_advance_log(integration_root)
    if not log.exists():
        return []
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContainmentError(f"cannot read integration advance log {log}: {exc}") from exc
    receipts: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        where = f"{log}:{number}"
        try:
            receipt = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContainmentError(f"{where}: malformed integration advance receipt: {exc}") from exc
        if not isinstance(receipt, dict):
            raise ContainmentError(f"{where}: integration advance receipt is not an object")
        fields = _RECEIPT_FIELDS
        if receipt.get("remote") == "origin":
            fields = (*fields, "origin_main")
        elif "origin_main" in receipt:
            raise ContainmentError(f"{where}: origin_main is only valid for remote 'origin'")
        for key in fields:
            if key not in receipt:
                raise ContainmentError(f"{where}: integration advance receipt lacks {key!r}")
        for key in fields:
            if key in ("pid", "at"):
                continue
            if not isinstance(receipt[key], str) or not receipt[key]:
                raise ContainmentError(f"{where}: integration advance receipt field {key!r} is not a non-empty string")
        if not isinstance(receipt["pid"], int) or isinstance(receipt["pid"], bool):
            raise ContainmentError(f"{where}: integration advance receipt field 'pid' is not an integer")
        _parse_receipt_time(receipt["at"], where)
        receipts.append(receipt)
    return receipts


@dataclass(frozen=True)
class HeadMoveAssessment:
    verified: bool
    reason: str | None
    evidence: dict[str, Any] | None


def _refused(reason: str) -> HeadMoveAssessment:
    return HeadMoveAssessment(verified=False, reason=reason, evidence=None)


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _receipt_chain(
    receipts: list[dict[str, Any]], start_head: str, current_head: str, window_start: datetime, delegated: Path
) -> list[dict[str, Any]]:
    windowed = [r for r in receipts if _parse_receipt_time(r["at"], "receipt") >= window_start]
    ordered = sorted(enumerate(windowed), key=lambda pair: (_parse_receipt_time(pair[1]["at"], "receipt"), pair[0]))
    ordered_receipts = [receipt for _, receipt in ordered]
    # Receipts that predate `start_head` inside the window (for example moves that a
    # recovery already accounted for) are skipped; from the first receipt starting at
    # `start_head` onward every receipt must chain, with no gap or extra entry.
    first = next((i for i, r in enumerate(ordered_receipts) if r["before"] == start_head), None)
    if first is None:
        raise ContainmentError(f"no receipt starts at the pre-run head {start_head[:12]}")
    chain = ordered_receipts[first:]
    expected = start_head
    for receipt in chain:
        if receipt["before"] != expected:
            raise ContainmentError(
                f"receipt chain is broken: expected a receipt starting at {expected[:12]}, found {receipt['before'][:12]}"
            )
        if receipt["remote"] != "origin":
            raise ContainmentError("receipt records a non-origin remote; detection-only verification requires origin main")
        if receipt["after"] != receipt["origin_main"] or (
            receipt["after"] != receipt["remote_main"]
        ):
            raise ContainmentError(
                f"receipt {receipt['before'][:12]}..{receipt['after'][:12]} did not land on the origin main it recorded"
            )
        if _inside(Path(receipt["actor_worktree"]).resolve(), delegated):
            raise ContainmentError(
                f"receipt {receipt['before'][:12]}..{receipt['after'][:12]} names the delegated worktree {delegated} as its actor"
            )
        expected = receipt["after"]
    if expected != current_head:
        raise ContainmentError(
            f"receipt chain ends at {expected[:12]} but the integration head is {current_head[:12]}"
        )
    return chain


def assess_head_move(
    integration_root: Path,
    before_head: str,
    after_head: str,
    *,
    containment: ContainmentResult,
    tier: str,
    delegated_worktree: Path | None = None,
    window_start: str | None = None,
) -> HeadMoveAssessment:
    """Decide whether a pure integration-head move is a verified concurrent advance.

    Common facts for every tier: the move is the only observed change (no new,
    changed or disappeared path), `before_head` is an ancestor of `after_head`,
    and `after_head` equals the local `refs/remotes/origin/<main>`.

    `hard` (native containment, Codex): those facts suffice, because the child
    provably could not write the integration checkout.

    `detection-only` (Claude): the child has a shell, so those facts do not say who
    moved the head. Additionally an unbroken chain of platform-written
    integration-advance receipts must lead from `before_head` to `after_head`,
    each dated at or after `window_start`, each landing on the origin main it
    recorded, and none acted from inside `delegated_worktree`. Unreadable or
    malformed receipts, and any gap, make the move unverified.
    """
    if tier not in (TIER_HARD, TIER_DETECTION_ONLY):
        raise ContainmentError(f"unknown enforcement tier {tier!r} for head-move classification")
    if containment.new_changes or containment.disappeared_changes:
        return _refused("integration paths were created, changed or disappeared")
    if not containment.head_moved:
        return _refused("integration head did not move")
    if not verify_remote_fast_forward(integration_root, before_head, after_head):
        return _refused("integration head is not a fast-forward equal to the recorded remote-tracking main")
    if tier == TIER_HARD:
        return HeadMoveAssessment(True, None, {"tier": tier, "before": before_head, "after": after_head, "receipts": []})
    if delegated_worktree is None or window_start is None:
        raise ContainmentError("detection-only head-move classification requires the delegated worktree and a window start")
    try:
        start = _parse_receipt_time(window_start, "window start")
        chain = _receipt_chain(
            read_integration_advances(integration_root), before_head, after_head, start, Path(delegated_worktree).resolve()
        )
    except ContainmentError as exc:
        return _refused(f"no verified receipt chain: {exc}")
    return HeadMoveAssessment(True, None, {"tier": tier, "before": before_head, "after": after_head, "receipts": chain})


def classify_head_move(
    integration_root: Path,
    before_head: str,
    after_head: str,
    *,
    containment: ContainmentResult,
    tier: str,
    delegated_worktree: Path | None = None,
    window_start: str | None = None,
) -> dict[str, Any] | None:
    """Evidence for a verified concurrent advance, or `None` when the move is unproven."""
    assessment = assess_head_move(
        integration_root,
        before_head,
        after_head,
        containment=containment,
        tier=tier,
        delegated_worktree=delegated_worktree,
        window_start=window_start,
    )
    return assessment.evidence if assessment.verified else None


def format_violation_message(assigned_worktree: Path, result: ContainmentResult) -> str:
    parts = [f"Delegated write containment violation: changes appeared outside assigned worktree {assigned_worktree}."]
    if result.new_changes:
        parts.append("New/changed paths: " + ", ".join(result.new_changes))
    if result.disappeared_changes:
        parts.append("Paths that disappeared during delegation: " + ", ".join(result.disappeared_changes))
    if result.head_moved:
        parts.append("Integration HEAD moved during delegation (something was committed there).")
    return " ".join(parts)


def record_containment_friction(
    integration_root: Path,
    assigned_worktree: Path,
    result: ContainmentResult,
    *,
    task: str | None = None,
    enforcement_tier: str | None = None,
    route: bool = True,
) -> None:
    """Record a local friction event for a containment violation.

    Must only be called after check_containment has already produced a definitive
    result (never before). Local JSONL append; does not require GitHub auth.

    `route` defaults to True and must stay that way for every production call site,
    so a real violation still routes through agent_friction.py's normal GitHub gate.
    Pass `route=False` only from hermetic test fixtures that intentionally create a
    synthetic violation; it appends `--no-route` so the event is recorded locally and
    never attempts a GitHub call, regardless of what `gh` the host resolves.
    """
    observation = format_violation_message(assigned_worktree, result)
    evidence = (
        f"new_changes={list(result.new_changes)!r} "
        f"disappeared_changes={list(result.disappeared_changes)!r} "
        f"head_moved={result.head_moved} "
        f"enforcement_tier={enforcement_tier!r}"
    )
    arguments = [
        sys.executable,
        str(integration_root / "scripts" / "agent_friction.py"),
        "record",
        "--category",
        "delegated-write-containment-violation",
        "--trigger",
        "unsafe-near-miss",
        "--severity",
        "high",
        "--scope",
        "platform",
        "--observation",
        observation,
        "--evidence",
        evidence,
        "--hypothesis",
        "A write-capable delegated subagent or subprocess wrote outside its assigned worktree.",
        "--proposal",
        "Review the delegation harness's containment wiring (cwd, PreToolUse hook, or sandbox writable root) for this delegation path.",
    ]
    if task:
        arguments.extend(["--task", task])
    if not route:
        arguments.append("--no-route")
    completed = subprocess.run(arguments, cwd=integration_root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        print(f"WARNING: could not record containment friction event: {detail}", file=sys.stderr)
