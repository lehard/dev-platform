"""Durable, source-repository final publication queue backed by GitHub PRs.

PR comments carry immutable admissions and coordinator update evidence. A single
GitHub Actions concurrency group owns branch updates and merge requests; this
module re-observes GitHub before every consequential action.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from _platform_common import current_worktree_root, read_platform_config, run_git
from publication_state import required_check_state_for_ref

PREFIX = "dev-platform-publication-queue:v1 "
QUEUE = "publication:queued"
ACTIVE = "publication:active"
BLOCKED = "publication:blocked"
WORKFLOW = ".github/workflows/publication-queue.yml"
CHECK_WAIT_SECONDS = 240


class QueueError(RuntimeError):
    pass


def _gh(root: Path, *args: str, data: dict[str, str] | None = None) -> Any:
    cmd = ["gh", *args]
    if data:
        for key, value in data.items():
            cmd += ["-f", f"{key}={value}"]
    result = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        raise QueueError(result.stderr.strip() or result.stdout.strip() or f"gh exit {result.returncode}")
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QueueError("GitHub returned non-JSON queue state") from exc


def _repo(root: Path) -> str:
    data = _gh(root, "repo", "view", "--json", "nameWithOwner")
    name = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not isinstance(name, str) or "/" not in name:
        raise QueueError("GitHub repository identity is unavailable")
    return name


def enabled(root: Path) -> bool:
    """Bootstrap safely: this change uses legacy finish until workflow is on main."""
    if read_platform_config(root).get("platform_version") != "source":
        return False
    return run_git(["cat-file", "-e", f"origin/main:{WORKFLOW}"], cwd=root, check=False).returncode == 0


def _comments(root: Path, repo: str, number: int) -> list[dict[str, Any]]:
    rows = _gh(root, "api", f"repos/{repo}/issues/{number}/comments?per_page=100")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise QueueError("PR queue comments are unavailable or exceed the bounded page")
    return [row for row in rows if isinstance(row, dict)]


def _events(root: Path, repo: str, number: int) -> list[dict[str, Any]]:
    events = []
    for row in _comments(root, repo, number):
        body = row.get("body")
        if not isinstance(body, str) or not body.startswith(PREFIX):
            continue
        try:
            payload = json.loads(body[len(PREFIX):])
        except json.JSONDecodeError as exc:
            raise QueueError(f"malformed publication marker on PR #{number}") from exc
        if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("number") != number:
            raise QueueError(f"invalid publication marker on PR #{number}")
        payload["comment_id"] = row.get("id")
        events.append(payload)
    return events


def _admission(events: list[dict[str, Any]], number: int) -> dict[str, Any] | None:
    """Concurrent retries share a slot; a blocked candidate may start a new one."""
    blocks = [event["comment_id"] for event in events if event.get("kind") == "block" and isinstance(event.get("comment_id"), int)]
    cutoff = max(blocks, default=0)
    admissions = [event for event in events if event.get("kind") == "admit" and isinstance(event.get("comment_id"), int) and event["comment_id"] > cutoff]
    if not admissions:
        return None
    first = min(admissions, key=lambda event: event["comment_id"])
    if not all(
        all(event.get(key) == first.get(key) for key in ("head", "branch"))
        for event in admissions
    ):
        raise QueueError(f"PR #{number} has conflicting admission evidence")
    return first


def _comment(root: Path, repo: str, number: int, payload: dict[str, Any]) -> None:
    payload = {"version": 1, "number": number, **payload}
    _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", data={"body": PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":"))})


def _label(root: Path, repo: str, number: int, label: str, *, present: bool) -> None:
    if present:
        _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/labels", data={"labels[]": label})
    else:
        result = subprocess.run(["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/{number}/labels/{label.replace(':', '%3A')}"], cwd=root, capture_output=True, text=True)
        if result.returncode and "404" not in result.stderr:
            raise QueueError(result.stderr.strip() or "cannot remove publication label")


def _ensure_labels(root: Path) -> None:
    for name, color in ((QUEUE, "a2eeef"), (ACTIVE, "fbca04"), (BLOCKED, "b60205")):
        result = subprocess.run(["gh", "label", "create", name, "--color", color, "--force"], cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise QueueError(result.stderr.strip() or f"cannot ensure label {name}")


def _pr(root: Path, repo: str, number: int) -> dict[str, Any]:
    data = _gh(root, "api", f"repos/{repo}/pulls/{number}")
    if not isinstance(data, dict) or data.get("number") != number:
        raise QueueError(f"PR #{number} is unavailable")
    return data


def _main(root: Path) -> str:
    result = run_git(["ls-remote", "origin", "refs/heads/main"], cwd=root)
    sha = result.stdout.split()[0] if result.stdout.split() else ""
    if len(sha) != 40:
        raise QueueError("authoritative main SHA is unavailable")
    return sha


def admit(root: Path, number: int, expected_head: str) -> dict[str, Any]:
    repo = _repo(root)
    pr = _pr(root, repo, number)
    if pr.get("state") != "open" or pr.get("base", {}).get("ref") != "main" or pr.get("head", {}).get("sha") != expected_head:
        raise QueueError("queue admission requires one open PR at the exact validated head against main")
    branch = pr.get("head", {}).get("ref")
    if not isinstance(branch, str) or not branch.startswith("agent/"):
        raise QueueError("queue admission requires an owned task branch")
    events = _events(root, repo, number)
    admitted = _admission(events, number)
    if admitted:
        if admitted.get("head") != expected_head:
            raise QueueError("PR has an earlier or ambiguous admission; resolve it before re-admission")
    else:
        base = _main(root)
        _ensure_labels(root)
        _comment(root, repo, number, {"kind": "admit", "head": expected_head, "base": base, "branch": branch})
        admitted = _admission(_events(root, repo, number), number)
        if admitted is None or admitted.get("head") != expected_head:
            raise QueueError("admission comment was not confirmed")
        _label(root, repo, number, BLOCKED, present=False)
    _label(root, repo, number, QUEUE, present=True)
    return {"number": number, "position_key": admitted["comment_id"], "head": expected_head, "state": "queued"}


def _queued(root: Path, repo: str) -> list[tuple[int, int, dict[str, Any]]]:
    rows = _gh(root, "pr", "list", "--state", "open", "--limit", "100", "--json", "number,labels")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise QueueError("open PR inventory is unavailable or exceeds the bounded limit")
    queue = []
    for row in rows:
        if not isinstance(row, dict) or QUEUE not in {label.get("name") for label in row.get("labels", []) if isinstance(label, dict)}:
            continue
        number = row.get("number")
        if not isinstance(number, int):
            raise QueueError("queued PR has no number")
        admission = _admission(_events(root, repo, number), number)
        if admission is None:
            raise QueueError(f"queued PR #{number} lacks a valid admission")
        queue.append((admission["comment_id"], number, admission))
    return sorted(queue)


def status(root: Path, number: int) -> dict[str, Any]:
    repo = _repo(root)
    pr = _pr(root, repo, number)
    events = _events(root, repo, number)
    admission = _admission(events, number)
    if admission is None:
        blocks = [event for event in events if event.get("kind") == "block"]
        if blocks:
            return {"state": "blocked", "number": number, "reason": blocks[-1].get("reason", "unknown")}
        return {"state": "not-admitted", "number": number}
    if pr.get("merged") or pr.get("state") == "closed":
        return {"state": "merged" if pr.get("merged") else "blocked", "number": number, "reason": "PR closed without merge" if not pr.get("merged") else ""}
    blocks = [e for e in events if e.get("kind") == "block" and e.get("comment_id", 0) > admission["comment_id"]]
    if blocks:
        return {"state": "blocked", "number": number, "reason": blocks[-1].get("reason", "unknown")}
    queue = _queued(root, repo)
    for index, (_, candidate, _) in enumerate(queue, 1):
        if candidate == number:
            labels = {label.get("name") for label in pr.get("labels", []) if isinstance(label, dict)}
            active = index == 1 and ACTIVE in labels
            return {"state": "active" if active else "waiting", "number": number, "position": index, "owner": "publication-queue workflow" if active else None}
    return {"state": "blocked", "number": number, "reason": "admitted PR lacks queue label"}



def local_status(root: Path, branch: str) -> dict[str, Any] | None:
    """Observe this task's admitted PR even after the coordinator updates its head."""
    result = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "number,baseRefName,headRefName"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        candidates = _gh(root, "pr", "list", "--state", "all", "--head", branch,
                         "--limit", "100", "--json", "number,baseRefName,headRefName")
        if not isinstance(candidates, list) or len(candidates) >= 100:
            raise QueueError("task PR inventory is unavailable or exceeds the bounded page")
        matches = [candidate for candidate in candidates if candidate.get("baseRefName") == "main"
                   and candidate.get("headRefName") == branch and isinstance(candidate.get("number"), int)]
        admitted = [candidate for candidate in matches
                    if any(event.get("kind") == "admit" for event in _events(root, _repo(root), candidate["number"]))]
        if len(admitted) > 1:
            raise QueueError("multiple admitted task PRs use the same branch")
        if not admitted:
            return None
        data = admitted[0]
    else:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise QueueError("task PR lookup returned invalid JSON") from None
    if data.get("baseRefName") != "main" or data.get("headRefName") != branch or not isinstance(data.get("number"), int):
        return None
    repo = _repo(root)
    events = _events(root, repo, data["number"])
    admission = _admission(events, data["number"])
    if admission is None:
        old = [event for event in events if event.get("kind") == "admit"]
        local_head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
        if old and old[-1].get("head") == local_head:
            return status(root, data["number"])
        return None
    if admission.get("head") != run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip():
        # After local fast-forward recovery the current head is a coordinator
        # descendant, so a matching update marker is also accepted.
        updates = [e for e in events if e.get("kind") == "update" and e.get("comment_id", 0) > admission["comment_id"]]
        if not updates or updates[-1].get("head") != run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip():
            raise QueueError("local task head is not the admitted or proven coordinator head")
    return status(root, data["number"])


def sync_merged_task(root: Path, branch: str, number: int) -> None:
    """Fast-forward only this clean task branch to its proven merged PR head."""
    repo = _repo(root)
    pr = _pr(root, repo, number)
    if not pr.get("merged") or pr.get("head", {}).get("ref") != branch:
        raise QueueError("exact task PR is not confirmed merged")
    remote_head = pr.get("head", {}).get("sha")
    events = _events(root, repo, number)
    admission = _admission(events, number)
    updates = [e for e in events if e.get("kind") == "update" and admission and e.get("comment_id", 0) > admission["comment_id"]]
    proven = updates[-1].get("head") if updates else admission.get("head") if admission else None
    if remote_head != proven:
        raise QueueError("merged PR head lacks coordinator update proof")
    local = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    if local == remote_head:
        return
    if run_git(["status", "--porcelain"], cwd=root).stdout.strip():
        raise QueueError("task worktree is dirty; cannot synchronize merged PR head")
    run_git(["fetch", "origin", f"pull/{number}/head"], cwd=root)
    if run_git(["rev-parse", "FETCH_HEAD"], cwd=root).stdout.strip() != remote_head:
        raise QueueError("fetched PR head differs from GitHub observation")
    if run_git(["merge-base", "--is-ancestor", local, remote_head], cwd=root, check=False).returncode:
        raise QueueError("coordinator head does not descend from local task head")
    run_git(["merge", "--ff-only", remote_head], cwd=root)


def _block(root: Path, repo: str, number: int, reason: str) -> dict[str, Any]:
    _comment(root, repo, number, {"kind": "block", "reason": reason[:500]})
    _label(root, repo, number, BLOCKED, present=True)
    _label(root, repo, number, ACTIVE, present=False)
    _label(root, repo, number, QUEUE, present=False)
    return {"state": "blocked", "number": number, "reason": reason}


def _task_paths(root: Path, repo: str, admission: dict[str, Any]) -> set[str]:
    # PR files include prior coordinator main merges. Compare immutable admission
    # endpoints so later unrelated main changes do not look task-owned.
    base, head = admission.get("base"), admission.get("head")
    if not all(isinstance(value, str) and len(value) == 40 for value in (base, head)):
        raise QueueError("admission endpoints are invalid")
    response = _gh(root, "api", f"repos/{repo}/compare/{base}...{head}")
    rows = response.get("files") if isinstance(response, dict) else None
    if not isinstance(rows, list) or len(rows) >= 300:
        raise QueueError("admitted task file inventory is unavailable or exceeds the bounded limit")
    paths = {row.get("filename") for row in rows if isinstance(row, dict)}
    if not paths or not all(isinstance(path, str) for path in paths):
        raise QueueError("PR has no provable task paths")
    return paths


def _prepare(root: Path, repo: str, number: int, admission: dict[str, Any], pr: dict[str, Any]) -> tuple[str, str]:
    head = pr.get("head", {}).get("sha")
    if not isinstance(head, str) or len(head) != 40:
        raise QueueError("PR head is unavailable")
    events = _events(root, repo, number)
    updates = [e for e in events if e.get("kind") == "update" and e.get("comment_id", 0) > admission["comment_id"]]
    proven = admission.get("head") if not updates else updates[-1].get("head")
    if head != proven:
        # A runner can die after GitHub updates the branch but before it writes
        # the update comment. Recover only a clean merge of proven head + main.
        run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
        parents = run_git(["rev-list", "--parents", "-n", "1", head], cwd=root).stdout.split()
        if len(parents) != 3 or parents[1] != proven:
            raise QueueError("PR head changed outside coordinator control")
        prior_main = parents[2]
        run_git(["fetch", "origin", "main"], cwd=root)
        if run_git(["merge-base", "--is-ancestor", prior_main, "origin/main"], cwd=root, check=False).returncode:
            raise QueueError("unrecorded branch update is not based on main")
        expected_tree = run_git(["merge-tree", "--write-tree", proven, prior_main], cwd=root, check=False)
        actual_tree = run_git(["rev-parse", f"{head}^{{tree}}"], cwd=root).stdout.strip()
        if expected_tree.returncode or expected_tree.stdout.splitlines()[0].strip() != actual_tree:
            raise QueueError("unrecorded branch update is not a clean main merge")
        _comment(root, repo, number, {"kind": "update", "previous": proven, "head": head, "base": prior_main})
    base = admission.get("base")
    if not isinstance(base, str) or len(base) != 40:
        raise QueueError("admission base is invalid")
    current_main = _main(root)
    if current_main == base and head == admission.get("head"):
        return head, current_main
    run_git(["fetch", "origin", "main"], cwd=root)
    if run_git(["merge-base", "--is-ancestor", base, current_main], cwd=root, check=False).returncode:
        raise QueueError("main no longer descends from admitted base")
    changed = set(run_git(["diff", "--name-only", f"{base}..{current_main}"], cwd=root).stdout.splitlines())
    overlap = changed & _task_paths(root, repo, admission)
    if overlap:
        raise QueueError("main changed task paths: " + ", ".join(sorted(overlap)[:8]))
    # If the previously prepared head already contains current main, do not
    # perform a redundant update or trigger another CI run.
    run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
    if run_git(["merge-base", "--is-ancestor", current_main, head], cwd=root, check=False).returncode == 0:
        return head, current_main
    _gh(root, "api", "-X", "PUT", f"repos/{repo}/pulls/{number}/update-branch", data={"expected_head_sha": head})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        observed = _pr(root, repo, number).get("head", {}).get("sha")
        if isinstance(observed, str) and observed != head:
            _comment(root, repo, number, {"kind": "update", "previous": head, "head": observed, "base": current_main})
            return observed, current_main
        time.sleep(3)
    raise QueueError("GitHub branch update is still pending; retry coordinator")


def worker(root: Path) -> dict[str, Any]:
    repo = _repo(root)
    queue = _queued(root, repo)
    if not queue:
        return {"state": "empty"}
    _, number, admission = queue[0]
    pr = _pr(root, repo, number)
    if pr.get("merged"):
        _label(root, repo, number, QUEUE, present=False)
        return {"state": "merged", "number": number}
    _label(root, repo, number, ACTIVE, present=True)
    try:
        head, base = _prepare(root, repo, number, admission, pr)
        deadline = time.monotonic() + CHECK_WAIT_SECONDS
        while True:
            state = required_check_state_for_ref(root, os.environ.copy(), str(number), head)
            if state.kind == "passed":
                break
            if state.kind == "failed":
                return _block(root, repo, number, "required check failed: " + state.detail)
            if state.kind == "not_registered":
                return _block(root, repo, number, "required check is not registered for the PR head")
            if state.kind == "unknown":
                raise QueueError("required check state is unknown: " + state.detail)
            if time.monotonic() >= deadline:
                return {"state": "waiting", "number": number, "reason": "required CI pending"}
            time.sleep(10)
        if _main(root) != base or _pr(root, repo, number).get("head", {}).get("sha") != head:
            return {"state": "waiting", "number": number, "reason": "main or PR head moved; coordinator will re-evaluate"}
        result = subprocess.run(["gh", "pr", "merge", str(number), "--squash", "--match-head-commit", head], cwd=root, text=True, capture_output=True)
        if _pr(root, repo, number).get("merged"):
            _label(root, repo, number, ACTIVE, present=False)
            _label(root, repo, number, QUEUE, present=False)
            return {"state": "merged", "number": number, "head": head}
        if result.returncode:
            return {"state": "waiting", "number": number, "reason": "protected merge refused; will re-evaluate: " + (result.stderr.strip() or "unknown")[:300]}
        return {"state": "waiting", "number": number, "reason": "merge accepted; awaiting GitHub confirmation"}
    except (QueueError, subprocess.CalledProcessError) as exc:
        return _block(root, repo, number, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Source repository final publication queue")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("admit")
    add.add_argument("--pr", type=int, required=True)
    add.add_argument("--head", required=True)
    show = sub.add_parser("status")
    show.add_argument("--pr", type=int, required=True)
    sub.add_parser("worker")
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "admit":
            result = admit(root, args.pr, args.head)
        elif args.command == "status":
            result = status(root, args.pr)
        else:
            result = worker(root)
    except QueueError as exc:
        print(json.dumps({"state": "error", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("state") in {"merged", "empty", "queued", "active", "waiting", "not-admitted"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
