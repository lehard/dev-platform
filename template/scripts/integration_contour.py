"""Autonomous integration contour: integration repair, lifecycle friction and post-merge jobs.

Coordinator-stack module (source repository only). Downstream and fixture checkouts never
import it at module level; callers import it lazily inside source-only branches.

* Integration repair resolves a real merge conflict (or a failing integration check) in a
  disposable checkout under the worker harness. Only the harness validates and pushes, with a
  lease on the claimed head. A repair that leaves task-content identity unchanged reuses the
  review/finalization evidence (checks rerun on the new head); a changed identity returns the
  candidate through review and finalization. Attempts are bounded.
* After the coordinator merges a candidate, retrospective, terminal-reconciliation and cleanup
  are ordinary worker jobs derived from trusted result receipts (no stored ledger), each
  idempotent so an interrupted run is simply offered again.
* Coordinator events are recorded as friction attributed to the candidate task and its
  Requirement through an explicitly registered sink.
"""
from __future__ import annotations

import functools
import json
from datetime import datetime
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from task_content_identity import equivalent_proofs
import lifecycle_workers as workers
import pr_review_gate as review_gate
import post_review_finalization as final
import publication_queue as queue

MAX_INTEGRATION_REPAIRS = queue.MAX_INTEGRATION_REPAIRS
COMPOSITION_IDENTITY = re.compile(r"requirement/BR-([1-9][0-9]*)$")
BRANCH_IDENTITY = re.compile(r"agent/br-([1-9][0-9]*)-t([1-9][0-9]*)-")
CONFLICT_MARKER = re.compile(r"^(<{7}|>{7}) ", re.MULTILINE)
POST_MERGE_KINDS = ("retrospective", "terminal-reconciliation", "cleanup")


class JobBlocked(RuntimeError):
    """A post-merge obligation cannot be completed truthfully; it is reported, never faked."""


class PostMergeEnvironmentError(workers.WorkerError):
    """The executing environment cannot run a post-merge job; it fails the run and spends no attempt."""


# Cleanup refusals that describe the executing machine, not the obligation.
ENVIRONMENT_CLEANUP_ERRORS = frozenset({"process-check-unavailable"})


# ---- lineage and friction attribution ---------------------------------------

def resolve_lineage(root: Path, branch: str) -> dict[str, str | None] | None:
    """The Requirement (and child Issue) a managed task branch belongs to, from its BR identity.

    ``agent/br-353-t6-change`` names a child; ``requirement/BR-353`` names the
    composition. Unmanaged branches have no lineage; managed lookup failures raise.
    """
    composition = COMPOSITION_IDENTITY.fullmatch(branch)
    match = composition or BRANCH_IDENTITY.match(branch)
    if not match:
        return None
    import managed_task
    import managed_work_identity
    import requirement_intake

    repository = managed_task.authoring_config(root).repository
    requirement = f"{repository}#{int(match[1])}"
    if composition:
        return {"requirement": requirement, "child": None}
    body = str(requirement_intake.fetch_issue(root, repository, int(match[1]))["body"])
    child = next((ref for ref, ordinal in managed_work_identity.RESERVATION.findall(body)
                  if int(ordinal) == int(match[2])), None)
    if child is None:
        raise JobBlocked(f"managed branch {branch} has no child reservation in {requirement}")
    return {"requirement": requirement, "child": child}


def default_friction_sink(root: Path):
    """A sink that persists coordinator events on the candidate PR, then mirrors them locally.

    Attribution is the public work identity of the candidate branch, so the sink
    needs no Backlog access or private configuration and never writes a private
    reference to the pull request. Durable first: a malformed managed branch or a
    failed evidence write raises before anything is recorded locally, so a
    transition is never published with machine-local-only evidence.
    """
    def sink(event: dict[str, Any]) -> None:
        import agent_friction
        import managed_work_identity
        import publication_queue

        task = event["task"]
        try:
            attribution = managed_work_identity.branch_attribution(task)
        except managed_work_identity.IdentityError as exc:
            raise publication_queue.QueueError(str(exc)) from exc
        record = publication_queue.post_evidence(root, event, attribution=attribution)
        agent_friction.append_coordinator_event(
            task=task, requirement=None, work_identity=attribution["work_identity"] if attribution else None,
            category=event["category"], triggers=event["triggers"],
            severity=event["severity"], observation=event["observation"], evidence=event["evidence"],
            hypothesis=event["hypothesis"], proposal=event["proposal"], dedupe_key=event["dedupe_key"],
            reason=event["reason"], candidate={"task": task, "number": event["number"], "head": event["head"]},
            event_id=record["event_id"])

    return sink


# ---- integration repair ------------------------------------------------------

def integration_brief(candidate: dict, conflicts: list[str]) -> dict:
    red = candidate.get("red_gate") or {}
    evidence = red.get("evidence")
    return {"state": candidate.get("state"), "head": candidate.get("head"),
            "attempts": candidate.get("attempts"), "red_gate": red.get("name"),
            "evidence": str(evidence.get("detail") if isinstance(evidence, dict) else evidence)[:800],
            "conflicts": conflicts[:20]}


# The sandboxed writer cannot read GitHub, so a red required check reaches it only as a log excerpt.
FAILED_LOG_LINES = 80
FAILED_LOG_CHARS = 6000
ACTIONS_JOB_LINK = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/actions/runs/(\d+)/job/(\d+)")


def read_failed_log(repo: str, run: str, job: str) -> str:
    """The failed-step log of one Actions job, read with the operator's ``gh``; an unreadable log raises."""
    done = subprocess.run(["gh", "run", "view", run, "--job", job, "--log-failed", "-R", repo],
                          capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise workers.WorkerError(f"integration-repair brief refused: the failed log of Actions job {job} is "
                                  "unreadable: " + (done.stderr or done.stdout).strip()[-300:])
    return done.stdout


def failed_check_evidence(red: dict, read_log: Callable[[str, str, str], str] = read_failed_log) -> list[dict]:
    """Each failed required check of a ``required-checks`` red gate with a bounded excerpt of its failed log.

    Refuses, naming the cause, when the red gate records no failed check, a check has no Actions job
    link, or its failed log is empty: a writer never starts without the evidence it has to fix.
    """
    evidence = red.get("evidence")
    checks = evidence.get("failed_checks") if isinstance(evidence, dict) else None
    if not isinstance(checks, list) or not checks:
        raise workers.WorkerError("integration-repair brief refused: the required-checks red gate records no failed "
                                  "check identity; a developer fix re-admission is the supported path")
    briefed = []
    for check in checks:
        name = check.get("name") if isinstance(check, dict) else None
        link = str(check.get("link") or "") if isinstance(check, dict) else ""
        match = ACTIONS_JOB_LINK.fullmatch(link)
        if not name or match is None:
            raise workers.WorkerError(f"integration-repair brief refused: failed check {name or check!r} has no "
                                      f"GitHub Actions job link to read its log from: {link or 'none'}")
        lines = read_log(*match.groups()).strip().splitlines()
        if not lines:
            raise workers.WorkerError(f"integration-repair brief refused: the failed log of check {name} is empty")
        briefed.append({"name": name, "workflow": check.get("workflow"), "state": check.get("state"), "link": link,
                        "log_excerpt": "\n".join(lines[-FAILED_LOG_LINES:])[-FAILED_LOG_CHARS:]})
    return briefed


def validate_integration_result(repo: Path, head: str, result: str, main_sha: str, allowed_paths) -> list[str]:
    """Accept only a descendant of ``head`` whose own edits stay inside the candidate's scope.

    Changes that merely take main's version of a path are main's work and need no scope; every
    path the repair itself decided (differing from both the claimed head and main) must be
    allowed and must not be a workflow or lifecycle-evidence file. The result must contain main
    whenever the claimed head did not.
    """
    for value in (head, result, main_sha):
        if not workers.HEAD.fullmatch(value):
            raise workers.WorkerError("invalid head")
    if result == head:
        raise workers.WorkerError("result has no new commits")
    if subprocess.run(["git", *workers.SAFE_GIT, "merge-base", "--is-ancestor", head, result], cwd=repo,
                      capture_output=True, check=False, stdin=subprocess.DEVNULL).returncode:
        raise workers.WorkerError("result is not a fast-forward from the expected head")

    def contains(ancestor: str, descendant: str) -> bool:
        return subprocess.run(["git", *workers.SAFE_GIT, "merge-base", "--is-ancestor", ancestor, descendant],
                              cwd=repo, capture_output=True, check=False, stdin=subprocess.DEVNULL).returncode == 0

    def diff(left: str) -> set[str]:
        return {p for p in workers._git(repo, "diff", "--name-only", "--no-renames", "-z", left, result).split("\0") if p}

    changed = diff(head)
    if contains(main_sha, result):
        changed &= diff(main_sha)
    elif not contains(main_sha, head):
        raise workers.WorkerError("result does not integrate current main")
    for path in sorted(changed):
        reason = workers._forbidden(path)
        if reason:
            raise workers.WorkerError(f"{reason}: {path}")
        if not workers._allowed(path, allowed_paths):
            raise workers.WorkerError(f"path outside candidate scope: {path}")
    return sorted(changed)


def _contains(checkout: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    return subprocess.run(["git", *workers.SAFE_GIT, "merge-base", "--is-ancestor", ancestor, descendant],
                          cwd=checkout, capture_output=True, check=False, stdin=subprocess.DEVNULL).returncode == 0


def execute_integration_repair(job: dict, brief: dict, *, source_repo: str, branch: str, allowed_paths,
                               llm_command, current_head: Callable[[], str], workdir: str,
                               runner=workers.run_in_session, env: dict[str, str] | None = None,
                               push_env: dict[str, str] | None = None, home_files=(),
                               before_push: Callable[[Path, str], None] | None = None,
                               claim_current: Callable[[], bool] = lambda: True,
                               launch: Callable[..., object] | None = None) -> dict:
    """Merge current main into a disposable checkout, let the writer resolve it, validate, push once."""
    root = Path(workdir).resolve()
    checkout = workers.prepare_checkout(source_repo, str(root), "integration-checkout", job["head"])
    target_branch = job.get("task_identity", {}).get("target_branch", "main") if isinstance(job.get("task_identity"), dict) else "main"
    workers._git(checkout, "fetch", "--no-tags", "origin", target_branch)
    main_sha = workers._git(checkout, "rev-parse", "FETCH_HEAD").strip()
    merging = False
    if not _contains(checkout, main_sha, job["head"]):
        merge = subprocess.run(["git", *workers.SAFE_GIT, *workers.HARNESS_IDENTITY, "merge", "--no-commit", "--no-ff", main_sha], cwd=checkout,
                               text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
        merging = (checkout / ".git" / "MERGE_HEAD").is_file()
        if merge.returncode and not merging:
            return {"status": "failed", "reason": "merge of main failed: " + (merge.stderr or merge.stdout).strip()[-300:]}
    conflicted = [p for p in workers._git(checkout, "diff", "--name-only", "--diff-filter=U").split() if p]
    if job["kind"] == workers.MERGE_ONLY_KIND and (conflicted or brief.get("red_gate") == "required-checks"):
        # An integration merge never starts a writer: the next attempt is a writer integration repair.
        needs = ("conflicts in: " + ", ".join(conflicted[:8])) if conflicted else "the required checks are red"
        return {"status": "failed", "reason": f"integration merge needs a writer integration repair: {needs}"}
    if conflicted or brief.get("red_gate") == "required-checks":
        command = shlex.split(llm_command) if isinstance(llm_command, str) else list(llm_command or [])
        if not command:
            raise workers.WorkerError("integration repair needs a configured writer command")
        prompt = ("Repair this candidate's integration with current main. Resolve every merge conflict keeping "
                  "both sides' intent, fix the failing integration check if one is named (its failed log is in "
                  "failed_checks[].log_excerpt), and leave the result "
                  "in the working tree (do not rely on commits; only file content is taken). Do not edit workflow or lifecycle evidence files. Brief: "
                  + json.dumps({**brief, "conflicts": conflicted or brief.get("conflicts", [])}, sort_keys=True))
        done = (launch or workers.run_llm)([*command, prompt], checkout, tmp=workers.writer_tmp(root), env=env, runner=runner,
                               home=workers.scratch_home(root, home_files))
        if done.returncode:
            return {"status": "failed", "reason": f"llm exited {done.returncode}"}
    # From here on the writer's checkout is data only: no git runs in it. Its files are imported into a
    # harness-owned clone that repeats the merge of main, so repository config, attributes drivers and
    # hooks planted by the writer can never execute, and every harness git runs without credentials.
    harness = workers.prepare_checkout(source_repo, str(root), "harness", job["head"])
    workers.harness_git(harness, "fetch", "--no-tags", "origin", target_branch)
    if workers.harness_git(harness, "rev-parse", "FETCH_HEAD").strip() != main_sha:
        return {"status": "discarded"}  # main moved while the writer ran; re-evaluated by the next run
    merging = False
    if not _contains(harness, main_sha, job["head"]):
        subprocess.run(["git", *workers.SAFE_GIT, *workers.HARNESS_IDENTITY, "merge", "--no-commit", "--no-ff", main_sha], cwd=harness,
                       text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL,
                       env=workers.credential_free_env(dict(os.environ), root / "harness-home"))
        merging = (harness / ".git" / "MERGE_HEAD").is_file()
        if not merging:
            return {"status": "failed", "reason": "merge of main failed in the harness"}
    workers.import_worktree(checkout, harness)
    for path in conflicted:
        target = harness / path
        if target.is_file() and CONFLICT_MARKER.search(target.read_text(encoding="utf-8", errors="replace")):
            return {"status": "failed", "reason": f"conflict markers remain in {path}"}
    workers.harness_git(harness, "add", "-A")
    if workers.harness_git(harness, "diff", "--name-only", "--diff-filter=U").strip():
        return {"status": "failed", "reason": "unresolved merge conflicts remain"}
    if not merging and not workers.harness_git(harness, "diff", "--cached", "--name-only").strip():
        return {"status": "no-change", "reason": "the writer produced no change"}
    workers.harness_git(harness, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                        "commit", "-q", "-m", "Integrate current main into the candidate")
    result_head = workers.harness_git(harness, "rev-parse", "HEAD").strip()
    if current_head() != job["head"]:
        return {"status": "discarded"}
    candidate_paths = {p for p in workers.harness_git(
        harness, "diff", "--name-only", "-z", workers.harness_git(harness, "merge-base", job["head"], main_sha).strip(),
        job["head"]).split("\0") if p}
    scope = [*allowed_paths, *sorted(candidate_paths), *brief.get("conflicts", []), *conflicted]
    validate_integration_result(harness, job["head"], result_head, main_sha, scope)
    if before_push is not None:
        before_push(harness, result_head)
    if not claim_current():
        return {"status": "discarded"}
    workers.push_validated(harness, branch, job["head"], result_head, runner=runner, env=push_env)
    return {"status": "pushed", "pushed_head": result_head, "main": main_sha}


def advance_after_repair(root: Path, repo: str, candidate: dict, head: str, fresh: dict, harness: Path | None,
                         *, adapter=queue) -> str:
    """Move a repaired candidate on: unchanged task content reuses evidence, changed content repeats review."""
    old = candidate.get("task_identity")
    managed = isinstance(old, dict) and isinstance(old.get("task_content"), dict)
    unchanged = (managed and isinstance(fresh.get("task_content"), dict)
                 and equivalent_proofs(harness or root, old["task_content"], fresh["task_content"]))
    if unchanged:
        # Review, selected checks and verification stay valid for identical content; the required
        # checks gate is never carried to the new head, so the coordinator reruns it on the merged head.
        gates = {name: {**gate, "identity": fresh} for name, gate in candidate.get("gates", {}).items()
                 if name != "required-checks" and review_gate.reusable(harness or root, gate, fresh)}
        state = "contribution-integration-pending" if fresh.get("kind") == "contribution" else "ready"
        adapter._transition(root, repo, candidate["number"], state, head, task_identity=fresh,
                            inherit_identity=False, gates=gates)
        return state
    if managed:
        final.return_to_review(harness or root, repo, candidate, head, fresh, adapter=adapter)
        return "review-pending"
    adapter._transition(root, repo, candidate["number"], "ready", head, task_identity=fresh, inherit_identity=False)
    return "ready"


def run_claimed_integration_repair(root: Path, repo: str, candidate: dict, job: dict, *, source_repo: str,
                                   branch: str, allowed_paths, llm_command, current_head, post_result,
                                   workdir: str, worker: str, adapter=queue, runner=None,
                                   provider: str | None = None, claim_current=None, push_env=None, home_files=(), env=None,
                                   conflicts: list[str] | None = None, launch=None,
                                   read_log: Callable[[str, str, str], str] = read_failed_log) -> dict:
    """Execute and advance one claimed integration-repair or integration-merge job, without the developer.

    An integration merge names no provider and is never given a writer command or launch. A writer
    repair of a red required check is briefed with each failed check's log excerpt; without that
    evidence the run raises before any writer starts and spends no repair attempt.
    """
    import subprocess as sp

    if job["kind"] not in {"integration-repair", workers.MERGE_ONLY_KIND}:
        raise workers.WorkerError(f"no integration-repair executor for {job['kind']}")
    number, identity = job["number"], job["task_identity"]
    if job["kind"] == workers.MERGE_ONLY_KIND:
        if llm_command or launch is not None or provider is not None:
            raise workers.WorkerError(f"PR #{number} integration-merge job runs no writer; got a writer command, "
                                      "launch or provider")
    else:
        workers.require_job_provider(job, provider)
    if claim_current is None:
        def claim_current():
            comments = adapter._comments(root, repo, number)
            return workers.i_won(job, worker, comments, trusted_apps=adapter.trusted_apps(root),
                                 trusted_writers=adapter.trusted_writers(
                                     root, comments, (workers.CLAIM_PREFIX,), repo=repo))
    if not claim_current():
        return {"status": "discarded"}
    observed = adapter._derive(root, adapter._pr(root, repo, number), adapter._comments(root, repo, number))
    if workers.build_job(observed) != job:
        return {"status": "discarded"}
    spent = observed.get("attempts", {}).get("integration-repair", 0)
    runner = runner or workers.run_in_session  # the writer's process group never outlives it

    def before_push(harness, head):
        if not claim_current():
            return
        workers.checkout_harness(harness, head)
        fresh = (review_gate.refresh_identity(harness, identity)
                 if isinstance(identity, dict) and identity.get("change") else {"branch": branch, "head": head})
        post_result(workers.result_body(job, worker, "validated-push", head, task_identity=fresh, provider=provider))

    def fail(reason: str) -> dict:
        if not claim_current():
            return {"status": "discarded"}
        post_result(workers.result_body(job, worker, "failed: " + reason[:200], provider=provider))
        if spent >= MAX_INTEGRATION_REPAIRS:
            adapter._block(root, repo, number, f"integration repair exhausted after {spent} attempts: {reason}"[:500],
                           head=job["head"])
            return {"status": "blocked-escalation", "reason": reason}
        # The next attempt is always a writer integration repair, so a merge-only round does not carry over.
        red = {key: value for key, value in (observed.get("red_gate") or {}).items() if key != "merge_only"} or None
        adapter._transition(root, repo, number, "integration-repair-pending", job["head"], task_identity=identity,
                            red_gate=red, set_attempts={"integration-repair": spent + 1})
        adapter.publish_job(root, repo, number, "integration-repair", job["head"], task_identity=identity,
                            attempt=spent + 1)
        return {"status": "failed", "reason": reason}

    brief = integration_brief(observed, conflicts or [])
    if job["kind"] == "integration-repair" and (observed.get("red_gate") or {}).get("name") == "required-checks":
        brief["failed_checks"] = failed_check_evidence(observed["red_gate"], read_log)
    try:
        outcome = execute_integration_repair(
            job, brief, source_repo=source_repo, branch=branch,
            allowed_paths=allowed_paths, llm_command=llm_command, current_head=current_head, workdir=workdir,
            runner=runner, env=env, push_env=push_env, home_files=home_files, before_push=before_push,
            claim_current=claim_current, launch=launch)
    except workers.WorkerError as exc:
        return fail(str(exc))
    if outcome["status"] == "discarded":
        return outcome
    if outcome["status"] != "pushed":
        return fail(outcome.get("reason", outcome["status"]))
    head = outcome["pushed_head"]
    if not workers.own_result_landed(current_head, job["head"], head) or not claim_current():
        return {**outcome, "status": "discarded"}
    adapter._comment(root, repo, number, {"kind": "update", "previous": job["head"], "head": head,
                                          "base": outcome["main"], "worker_job": workers.job_id(job)})
    harness = Path(workdir).resolve() / "harness"
    workers.checkout_harness(harness, head)
    fresh = (review_gate.refresh_identity(harness, identity)
             if isinstance(identity, dict) and identity.get("change") else {"branch": branch, "head": head})
    state = advance_after_repair(root, repo, observed, head, fresh, harness, adapter=adapter)
    post_result(workers.result_body(job, worker, "integrated", head, provider=provider))
    return {"status": "integrated", "pushed_head": head, "state": state}


def recover_integration_repair(root: Path, repo: str, number: int, observed: dict, comments: list[dict],
                               *, adapter=queue) -> bool:
    """Persist a validated, content-unchanged repair push whose own advancement was interrupted.

    ``derive_candidate`` recognises the harness's validated-push receipt; the coordinator then
    records the missing update marker and the ``ready`` record so the head is a proven
    coordinator head. Idempotent. Returns whether anything was recorded.
    """
    current = adapter._derive(root, observed, comments)
    if not str(current.get("reason", "")).startswith("recover validated integration-repair push"):
        return False
    head = current["head"]
    lineage = adapter._latest(root, number, comments)
    if lineage is None:
        # The derived candidate recognised this repair push from a recorded job, so a missing record is a lost record.
        raise adapter.QueueError(f"integration repair recovery for PR #{number} has no recorded lineage head")
    if not any(event.get("kind") == "update" and event.get("head") == head
               for event in adapter._events(root, repo, number)):
        adapter._comment(root, repo, number, {"kind": "update", "previous": lineage.get("head"), "head": head,
                                              "worker_job": "integration-repair-recovery"})
    adapter._transition(root, repo, number, "ready", head, task_identity=current["task_identity"],
                        inherit_identity=False, gates=current["gates"])
    return True


# ---- post-merge obligations --------------------------------------------------

class LifecycleOps:
    """Operator-side adapters for post-merge jobs; tests and callers may replace any method."""

    def requirement_started_at(self, root: Path, requirement: str) -> datetime:
        """When the Requirement Issue was created: nothing of the Requirement predates it; unprovable blocks."""
        import managed_task
        from agent_friction import parse_time

        try:
            repository, number = managed_task.issue_ref(requirement)
            return parse_time(managed_task.fetch_issue(root, repository, number)["created_at"])
        except (managed_task.ManagedTaskError, KeyError, TypeError, ValueError) as exc:
            raise JobBlocked(f"cannot prove when {requirement} started: {exc}") from exc

    def candidate_admitted_at(self, root: Path, number: int) -> datetime:
        """When PR #number received its first trusted coordinator record; an unprovable start blocks."""
        from agent_friction import parse_time
        from candidate_lifecycle import MalformedMarkerError, first_record

        comments = queue._comments(root, queue._repo(root), number)
        try:
            record = first_record(number, comments, trusted_apps=queue.trusted_apps(root),
                                  trusted_writers=queue.trusted_writers(root, comments))
        except MalformedMarkerError as exc:
            raise JobBlocked(f"cannot prove when PR #{number} was admitted: {exc}") from exc
        try:
            return parse_time(record["at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise JobBlocked(f"cannot prove when PR #{number} was admitted: {exc}") from exc

    def lineage(self, root: Path, branch: str) -> dict | None:
        return resolve_lineage(root, branch)

    def children(self, root: Path, requirement: str) -> list[str]:
        import requirement_intake

        parent = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(requirement))
        return list(requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"])

    def child_closed(self, root: Path, child: str) -> bool:
        import requirement_intake

        issue = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(child))
        return str(issue.get("state", "")).upper() == "CLOSED"

    def terminal_recorded(self, root: Path, number: int) -> bool:
        """Whether a trusted lifecycle result records a successful terminal reconciliation of PR #number."""
        comments = queue._comments(root, queue._repo(root), number)
        apps = queue.trusted_apps(root)
        writers = queue.trusted_writers(root, comments, (workers.RESULT_PREFIX,), repo=queue._repo(root))
        prefix = f"pr{number}:terminal-reconciliation:"
        for row in comments:
            body = row.get("body")
            if not isinstance(body, str) or not body.startswith(workers.RESULT_PREFIX):
                continue
            if not workers.trusted_marker_comment(row, apps, writers):
                continue
            try:
                record = json.loads(body[len(workers.RESULT_PREFIX):])
            except json.JSONDecodeError as exc:
                raise JobBlocked(f"PR #{number} has a malformed trusted lifecycle result") from exc
            if (isinstance(record, dict) and str(record.get("job", "")).startswith(prefix)
                    and str(record.get("outcome", "")).startswith("task-recorded")):
                return True
        return False

    def direct_source(self, root: Path, number: int, head: str, change: str) -> str:
        """The private source Issue of a merged direct managed task, proven from its archived lineage handle."""
        import private_lineage

        from _platform_common import run_git

        run_git(["fetch", "origin", f"pull/{number}/head"], cwd=root)
        if run_git(["rev-parse", "FETCH_HEAD"], cwd=root).stdout.strip() != head:
            raise JobBlocked(f"PR #{number} fetched head differs from the merged head")
        listed = run_git(["ls-tree", "-d", "--name-only", head, "openspec/changes/archive/"], cwd=root).stdout.split()
        archived = [path for path in listed if path.rsplit("/", 1)[-1].endswith(f"-{change}")]
        if len(archived) != 1:
            raise JobBlocked(f"PR #{number} merged head has {len(archived)} archives of change {change}")
        shown = run_git(["show", f"{head}:{archived[0]}/.managed-task.json"], cwd=root, check=False)
        try:
            handle = json.loads(shown.stdout).get("private_lineage_handle") if not shown.returncode else None
        except ValueError:
            handle = None
        if not isinstance(handle, str):
            raise JobBlocked(f"PR #{number} archived change {change} carries no private lineage handle")
        try:
            return private_lineage.issue_for_handle(root, handle, change)
        except private_lineage.PrivateLineageError as exc:
            raise JobBlocked(str(exc)) from exc

    def reconcile_child(self, root: Path, child: str) -> None:
        import managed_project_status
        import requirement_terminal

        observed = managed_project_status.reconcile(root, "Done", source_issue=child)
        if observed is None or observed.current_status != "Done":
            raise JobBlocked(f"{child} Project Done reconciliation failed")
        if not self.child_closed(root, child):
            requirement_terminal._close_issue(root, child)

    def requirement_checkpoint(self, root: Path, requirement: str, event_ids: list[str]) -> None:
        import requirement_retrospective

        requirement_retrospective.checkpoint(
            root, requirement=requirement, result="findings" if event_ids else "none", event_ids=event_ids,
            review_note="Automated Requirement retrospective over recorded lifecycle events of the Requirement and its linked children.")

    def requirement_checkpointed(self, root: Path, requirement: str) -> bool:
        import requirement_retrospective

        try:
            requirement_retrospective.require_checkpoint(root, requirement=requirement)
        except requirement_retrospective.RequirementRetrospectiveError:
            return False
        return True

    def reconcile_parent(self, root: Path, requirement: str, merged_children: set[str]) -> None:
        import requirement_terminal

        requirement_terminal.reconcile_parent(root, requirement=requirement, merged_children=merged_children)

    def cleanup(self, root: Path, branch: str, number: int, merged_head: str) -> dict:
        return local_cleanup(root, branch, number, merged_head)


def local_cleanup(root: Path, branch: str, number: int, merged_head: str) -> dict:
    """Remove this task's local worktree and branch only when proven delivered, clean and idle.

    The local head must be contained in the merged PR head; worktree_cleanup then refuses a dirty,
    active, locked or identity-mismatched target. Nothing outside the managed worktree directory
    and nothing but this branch's worktree is touched.
    """
    import worktree_cleanup as cleanup
    from _platform_common import machine_path, run_git

    matches = [w for w in cleanup._list_worktrees(root) if w.branch == branch]
    if not matches:
        return {"status": "already-clean", "removed": [], "errors": []}
    run_git(["fetch", "origin", f"pull/{number}/head"], cwd=root)
    if run_git(["rev-parse", "FETCH_HEAD"], cwd=root).stdout.strip() != merged_head:
        raise JobBlocked("fetched PR head differs from the merged head")
    removed: list[str] = []
    errors: list[dict] = []
    managed_root = machine_path("worktrees", root)
    for worktree in matches:
        if not cleanup._path_within(worktree.path, managed_root):
            errors.append({"path": str(worktree.path), "error": "outside-managed-directory"})
        elif run_git(["merge-base", "--is-ancestor", worktree.head, merged_head], cwd=root, check=False).returncode:
            errors.append({"path": str(worktree.path), "error": "local-commits-not-in-merged-pr"})
        else:
            _, target = cleanup.defer_completed_task(root, worktree.path, branch)
            result = cleanup._cleanup_target(root, target)
            removed += list(result.get("removed", []))
            errors += list(result.get("errors", []))
    return {"status": "blocked" if errors else "cleaned", "removed": removed, "errors": errors}


def _events_for(task: str, children=()) -> list[dict]:
    import agent_friction

    return agent_friction.events_for_task(task, children)


def ensure_requirement_checkpoint(ops: LifecycleOps, root: Path, requirement: str, children: list[str]) -> bool:
    """Record the Requirement retrospective from recorded events; ambiguity or gaps block, never become ``none``."""
    import agent_friction
    import requirement_retrospective

    try:
        ambiguous = [str(e.get("id")) for e in agent_friction.ambiguous_attribution_events(ops.requirement_started_at(root, requirement))]
    except agent_friction.FrictionLogError as exc:
        raise JobBlocked(str(exc)) from exc
    if ambiguous:
        raise JobBlocked("ambiguous friction attribution needs a human decision: " + ", ".join(ambiguous[:5]))
    try:
        ids = list(dict.fromkeys(str(e.get("id")) for e in _events_for(requirement, children)))
    except (agent_friction.DurableEvidenceError, agent_friction.FrictionLogError) as exc:
        raise JobBlocked(str(exc)) from exc
    try:
        ops.requirement_checkpoint(root, requirement, ids)
    except requirement_retrospective.RequirementRetrospectiveError as exc:
        raise JobBlocked(str(exc)) from exc
    return True


def run_retrospective(ops: LifecycleOps, root: Path, number: int, branch: str, head: str) -> str:
    import agent_friction

    try:
        ambiguous = [str(e.get("id")) for e in agent_friction.ambiguous_attribution_events(ops.candidate_admitted_at(root, number))]
        if ambiguous:
            raise JobBlocked("ambiguous friction attribution needs a human decision: " + ", ".join(ambiguous[:5]))
        ids = list(dict.fromkeys(str(e.get("id")) for e in _events_for(branch)))
    except agent_friction.FrictionLogError as exc:
        raise JobBlocked(str(exc)) from exc
    try:
        agent_friction.record_checkpoint(
            branch, root, event_ids=ids, head=head, bind_content=False,
            review_note="Automated coordinator retrospective over the recorded review, repair, integration, "
                        "fallback and retry events of this candidate.")
    except SystemExit as exc:
        raise JobBlocked(str(exc)) from exc
    lineage = ops.lineage(root, branch)
    if not lineage or not lineage.get("requirement"):
        return "task-recorded"
    children = ops.children(root, lineage["requirement"])
    own = lineage.get("child")
    if own and all(child == own or ops.child_closed(root, child) for child in children):
        ensure_requirement_checkpoint(ops, root, lineage["requirement"], children)
        return "task-and-requirement-recorded"
    return "task-recorded; requirement retrospective awaits remaining children"


def quick_task(task_identity) -> bool:
    """Whether a queue task identity is a quick task's: branch and head only, no managed change.

    Admission never degrades a managed candidate to this identity and transitions inherit it,
    so a missing change is a quick task, never a managed candidate that lost its lineage.
    """
    return isinstance(task_identity, dict) and "change" not in task_identity and "kind" not in task_identity


def run_direct_terminal(ops: LifecycleOps, root: Path, number: int, head: str, change: str) -> str:
    """Terminal reconciliation of a direct managed task (no BR branch identity) through its opaque lineage (BR-975).

    A trusted successful terminal result for this PR ends the job before any Backlog walk. Public
    receipts and messages name only the private Issue number, never the handle or the Backlog.
    """
    if ops.terminal_recorded(root, number):
        return "task-recorded: already reconciled"
    child = ops.direct_source(root, number, head, change)
    issue = "#" + child.rsplit("#", 1)[1]
    try:
        ops.reconcile_child(root, child)
    except JobBlocked as exc:
        raise JobBlocked(f"Issue {issue} Project Done reconciliation failed") from exc
    print(f"PR #{number}: direct managed source Issue {issue} reconciled", file=sys.stderr)
    return f"task-recorded: Issue {issue}"


def run_terminal(ops: LifecycleOps, root: Path, number: int, branch: str, head: str, *, task_identity) -> str:
    lineage = ops.lineage(root, branch)
    if lineage is None and quick_task(task_identity):
        return "no-source-issue: quick task"
    if lineage is None and isinstance(task_identity, dict) and isinstance(task_identity.get("change"), str):
        return run_direct_terminal(ops, root, number, head, task_identity["change"])
    if not lineage or not lineage.get("child"):
        raise JobBlocked("cannot resolve the task's source Issue; reconcile its Project state manually")
    child = lineage["child"]
    ops.reconcile_child(root, child)
    requirement = lineage.get("requirement")
    if not requirement:
        return "child-reconciled"
    children = ops.children(root, requirement)
    if not all(c == child or ops.child_closed(root, c) for c in children):
        return "child-reconciled; requirement awaits remaining children"
    if not ops.requirement_checkpointed(root, requirement):
        ensure_requirement_checkpoint(ops, root, requirement, children)
    from requirement_terminal import OwnerAcceptancePending
    try:
        ops.reconcile_parent(root, requirement, {child})
    except OwnerAcceptancePending as exc:
        return awaits_owner_acceptance(exc)
    except RuntimeError as exc:
        raise JobBlocked(str(exc)) from exc
    return "requirement-reconciled"


def awaits_owner_acceptance(exc) -> str:
    """A completed terminal outcome: the Requirement waits for its owner's acceptance decision (BR-943).

    No attempt is spent on a human wait; ``requirement_terminal.py accept`` closes the Requirement later.
    """
    return "requirement-awaits-owner-acceptance: " + ", ".join(exc.items)


def run_cleanup(ops: LifecycleOps, root: Path, number: int, branch: str, head: str) -> str:
    result = ops.cleanup(root, branch, number, head)
    environment = sorted({str(item.get("error")) for item in result.get("errors", [])} & ENVIRONMENT_CLEANUP_ERRORS)
    if environment:
        raise PostMergeEnvironmentError(
            f"post-merge cleanup of PR #{number} cannot run on this machine ({', '.join(environment)}): the active-process "
            "check needs lsof on PATH; fix the environment, no attempt was recorded")
    if result.get("errors"):
        raise JobBlocked("local cleanup refused: " + json.dumps(result["errors"], sort_keys=True)[:300])
    return "cleaned" if result.get("removed") else "already-clean"


def run_claimed_post_merge(root: Path, repo: str, candidate: dict, job: dict, *, branch: str, post_result,
                           ops: LifecycleOps | None = None, adapter=queue, worker: str,
                           claim_current=None) -> dict:
    """Execute one claimed post-merge job. A refusal is a blocked receipt, an error a failed one; both are retried within a bound."""
    kind = job["kind"]
    if kind not in POST_MERGE_KINDS:
        raise workers.WorkerError(f"no post-merge executor for {kind}")
    if claim_current is None:
        def claim_current():
            comments = adapter._comments(root, repo, job["number"])
            return workers.i_won(job, worker, comments, trusted_apps=adapter.trusted_apps(root),
                                 trusted_writers=adapter.trusted_writers(
                                     root, comments, (workers.CLAIM_PREFIX,), repo=repo))
    if not claim_current():
        return {"status": "discarded"}
    if candidate.get("state") != "merged" or workers.build_job(candidate) != job:
        return {"status": "discarded"}
    ops = ops or LifecycleOps()
    run = {"retrospective": run_retrospective, "cleanup": run_cleanup,
           "terminal-reconciliation": functools.partial(run_terminal, task_identity=job["task_identity"])}[kind]
    try:
        if isinstance(job.get("task_identity"), dict) and job["task_identity"].get("kind") == "requirement-composition":
            import tempfile
            from requirement_composition import candidate_manifest, reconcile_composition
            with tempfile.TemporaryDirectory(prefix="composition-terminal-job-") as temporary:
                checkout = workers.prepare_checkout(f"https://github.com/{repo}.git", temporary, "harness", job["head"],
                                                    contract_from=root / ".dev-platform.toml")
                manifest = candidate_manifest(checkout, job["task_identity"]["requirement"])
            if kind == "terminal-reconciliation":
                from requirement_terminal import OwnerAcceptancePending
                try:
                    outcome = reconcile_composition(root, repo, manifest, job["head"], job["number"], adapter=adapter)["status"]
                except OwnerAcceptancePending as exc:
                    outcome = awaits_owner_acceptance(exc)
            else:
                # The manifest is bounded by its mandatory set. Retrying after interruption
                # repeats idempotent child operations before closing the parent obligation.
                for child in manifest["children"]:
                    if not claim_current():
                        return {"status": "discarded"}
                    run(ops, root, child["pr_number"], child["source_branch"], child["head"])
                outcome = run(ops, root, job["number"], branch, job["head"])
                if kind == "retrospective":
                    # The merged composition delivered every mandatory child: this job is the only place the
                    # Requirement retrospective is recorded (BR-950), before terminal reconciliation closes it.
                    from requirement_contributions import private_manifest
                    exact = private_manifest(root, manifest)
                    ensure_requirement_checkpoint(ops, root, exact["requirement"],
                                                  [c["source_issue"] for c in exact["children"]])
                    outcome = "task-and-requirement-recorded"
            status = "done"
        else:
            outcome, status = run(ops, root, job["number"], branch, job["head"]), "done"
    except JobBlocked as exc:
        outcome, status = "blocked: " + str(exc)[:200], "blocked"
    except PostMergeEnvironmentError:
        raise  # no receipt: the caller releases the claim and fails visibly
    except Exception as exc:  # a lost operator credential or network error is retried, never fatal
        outcome, status = "failed: " + str(exc)[:200], "failed"
    if not claim_current():
        return {"status": "discarded"}
    post_result(workers.result_body(job, worker, outcome))
    return {"status": status, "outcome": outcome}
