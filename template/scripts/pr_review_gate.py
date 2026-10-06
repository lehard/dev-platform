"""Coordinator review/repair gate using the shared candidate and worker contracts.

GitHub operations live in publication_queue; callers can inject that adapter and
worker commands. Content proofs, never labels or a head alone, authorize reuse.
"""
from __future__ import annotations

import json
from pathlib import Path

from task_content_identity import equivalent_proofs, review_content_identity
import lifecycle_workers as workers
import publication_queue as queue

MAX_ROUNDS = 3


def managed_candidate(root: Path) -> bool:
    from _platform_common import read_platform_config
    from managed_task import resolve_canonical_provenance

    config = read_platform_config(root)
    provenance = resolve_canonical_provenance(root)
    return (config.get("platform_version") == "source" and queue.enabled(root)
            and provenance is not None and provenance.lifecycle == "active")


def task_identity(root: Path, change: str) -> dict:
    proof = review_content_identity(root, change)
    if proof is None:
        raise workers.WorkerError("cannot prove candidate task-content identity")
    return {"change": change, "task_content": proof}


def reusable(root: Path, gate: dict | None, identity: dict) -> bool:
    return (isinstance(gate, dict) and gate.get("result") == "passed"
            and isinstance(gate.get("identity"), dict)
            and gate["identity"].get("change") == identity.get("change")
            and equivalent_proofs(root, gate["identity"].get("task_content"), identity.get("task_content")))


def file_reference(root: Path, path: Path) -> dict:
    """A compact, content-addressed reference to evidence that lives in the candidate."""
    import hashlib

    data = path.read_bytes()
    try:
        relative = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        relative = path.name
    return {"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def compact_reports(reports: dict) -> dict:
    """Reviewer reports reduced to what lifecycle readers use; full reports stay committed evidence."""
    from independent_review import report_digest

    compact = {}
    for name, report in reports.items():
        if not isinstance(report, dict) or "report_sha256" in report:
            compact[name] = report
            continue
        entry = {key: report[key] for key in ("availability", "perspective") if key in report}
        if isinstance(report.get("limitation"), str):
            entry["limitation"] = report["limitation"][:300]
        entry["report_sha256"] = report_digest(report)
        entry["findings"] = [{"id": finding.get("id"), "severity": finding.get("severity"),
                              "summary": str(finding.get("summary") or finding.get("title") or "")[:300],
                              "evidence": str(finding.get("evidence") or "")[:500]}
                             for finding in report.get("findings", []) if isinstance(finding, dict)]
        compact[name] = entry
    return compact


def repair_brief(running: dict) -> dict:
    """The compact record a repair writer needs: identity digest and each finding's id, summary, evidence."""
    identity = running.get("task_identity")
    content = identity.get("task_content") if isinstance(identity, dict) else None
    evidence = (running.get("red_gate") or {}).get("evidence")
    if not isinstance(evidence, dict):
        evidence = (running.get("gates", {}).get("review") or {}).get("evidence")
    findings = [{"perspective": name, **{k: finding.get(k) for k in ("id", "severity", "summary", "evidence")}}
                for name, report in (evidence.items() if isinstance(evidence, dict) else [])
                if isinstance(report, dict) for finding in report.get("findings", []) if isinstance(finding, dict)]
    return {"state": running.get("state"), "head": running.get("head"), "attempts": running.get("attempts"),
            "change": identity.get("change") if isinstance(identity, dict) else None,
            "task_content_digest": content.get("digest") if isinstance(content, dict) else None,
            "findings": findings}


def handoff_gates(root: Path, change: Path) -> tuple[dict, dict]:
    """Validate developer evidence before publication; never manufacture a receipt."""
    from openspec_lifecycle import require_automated_evidence, verification_passed

    if not verification_passed(change):
        raise workers.WorkerError("developer handoff requires successful semantic verification and its method")
    require_automated_evidence(change, root=root)
    identity = task_identity(root, change.name)
    helper = root / "scripts/agent_friction.py"
    if not helper.is_file():
        raise workers.WorkerError("developer handoff requires the friction checkpoint helper")
    import subprocess

    command = ["python3", str(helper), "assert-checkpoint", "--exact-head"]
    checkpoint = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                text=True, capture_output=True, check=False)
    if checkpoint.returncode:
        raise workers.WorkerError(checkpoint.stderr.strip() or checkpoint.stdout.strip() or "developer friction checkpoint unavailable")
    head = workers._git(root, "rev-parse", "HEAD").strip()
    checks_path, verification_path = change / "automated-checks.json", change / "verification.md"
    evidence = json.loads(checks_path.read_text())
    if not equivalent_proofs(root, evidence.get("gate_task_content"), identity["task_content"]):
        raise workers.WorkerError("selected checks lack current task-content binding; rerun select_checks with --evidence")
    return identity, {
        "developer-friction": {"result": "passed", "identity": identity,
                               "evidence": {"head": head, "command": command}},
        "selected-checks": {"result": "passed", "identity": identity, "evidence": file_reference(root, checks_path)},
        "semantic-verification": {"result": "passed", "identity": identity,
                                  "evidence": file_reference(root, verification_path)},
    }


def offer(root: Path, repo: str, number: int, head: str, identity: dict,
          kind: str, *, gates: dict | None = None, red_gate: dict | None = None,
          attempt: int | None = None, providers=None, set_attempts=None, adapter=queue) -> dict | None:
    """Publish state first, then the shared head-bound job (both resumable)."""
    record = adapter._transition(root, repo, number, kind + "-pending", head,
                                 task_identity=identity, inherit_identity=False,
                                 gates=gates, red_gate=red_gate, attempt=kind, set_attempts=set_attempts)
    if record is None:
        return None
    return adapter.publish_job(root, repo, number, kind, head, task_identity=identity, attempt=attempt,
                               providers=providers)


def review_outcome(reports: dict, rounds: int, *, rejected: bool = False) -> str:
    """Unavailable runtimes retry; material findings are bounded or escalated."""
    if rejected:
        return "blocked-escalation"
    if not reports or any(report.get("availability") != "available" for report in reports.values()):
        return "blocked-retryable"
    material = any(finding.get("severity") == "material" for report in reports.values()
                   for finding in report.get("findings", []))
    return "blocked-escalation" if material and rounds >= MAX_ROUNDS else "repair-pending" if material else "finalize-pending"


def complete_review(root: Path, repo: str, candidate: dict, reports: dict, head: str, *,
                    rejected: bool = False, adapter=queue) -> dict | None:
    identity = candidate["task_identity"]
    attempts = candidate.get("attempts", {})
    reports = compact_reports(reports)
    providers = (candidate.get("next_job") or {}).get("providers", ["unresolved-originating-task-route"])
    rounds = attempts.get("repair", 0) + 1
    state = review_outcome(reports, rounds, rejected=rejected)
    # Only consecutive unavailable attempts spend the retry budget; an available review resets it.
    streak = attempts.get("review-unavailable", 0) + 1 if state == "blocked-retryable" else 0
    streak_update = {"review-unavailable": streak}
    gate = {"result": "passed" if state == "finalize-pending" else "failed",
            "identity": identity, "evidence": reports}
    red = None if state == "finalize-pending" else {"name": "review", "identity": identity, "evidence": reports}
    if state == "repair-pending":
        return offer(root, repo, candidate["number"], head, identity, "repair",
                     gates={**candidate.get("gates", {}), "review": gate}, red_gate=red,
                     providers=providers, set_attempts=streak_update, adapter=adapter)
    record = adapter._transition(root, repo, candidate["number"], state, head,
                                 task_identity=identity, inherit_identity=False,
                                 gates={**candidate.get("gates", {}), "review": gate}, red_gate=red, set_attempts=streak_update)
    if record is not None and state == "blocked-retryable" and streak < MAX_ROUNDS:
        # A fresh attempt must differ from the completed job, even on the same head.
        return adapter.publish_job(root, repo, candidate["number"], "review", head,
                                   task_identity=identity, attempt=attempts.get("review", 0) + 1,
                                   providers=providers)
    return record


def current_rejections(reports: dict, dispositions: list[dict]) -> bool:
    from independent_review import report_digest, _accepted_rejection

    return any(_accepted_rejection(dispositions, perspective, finding.get("id"), report_digest(report))
               for perspective, report in reports.items() for finding in report.get("findings", [])
               if finding.get("severity") == "material")


def execute_review(checkout: Path, job: dict, *, source_repo: str, branch: str,
                   current_head, runner, push_env=None, launcher=None, review_config=None, before_push=None,
                   claim_current=lambda: True) -> dict:
    """Run the existing reviewer; only the harness commits and pushes evidence."""
    from independent_review_runner import run_review
    from independent_review import PERSPECTIVES, _validate_report, read_dispositions

    checkout = checkout.resolve()
    identity = job["task_identity"]
    change = checkout / "openspec" / "changes" / identity["change"]
    actual = task_identity(checkout, identity["change"])
    if actual != identity:
        raise workers.WorkerError("review checkout does not match the published task identity")
    if launcher is None:
        from independent_review_runner import subprocess_launcher
        import os

        clean = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
        launcher = lambda argv, cwd, timeout: subprocess_launcher(argv, cwd, timeout, env=clean)
    reports = run_review(checkout, change, launcher=launcher, config=review_config)
    request = json.loads((change / "independent-review-request.json").read_text())
    if set(reports) != set(PERSPECTIVES) or any(
            _validate_report(reports[p], request, p, required=True) for p in PERSPECTIVES):
        raise workers.WorkerError("review evidence does not prove both independent perspectives")
    contexts = [reports[p]["reviewer"]["context_id"] for p in PERSPECTIVES]
    if len(set(contexts)) != len(contexts):
        raise workers.WorkerError("review perspectives reused the same context")
    rejected = current_rejections(reports, read_dispositions(change))
    changed = [p for p in workers._git(checkout, "diff", "--name-only").splitlines() if p]
    prefix = change.relative_to(checkout).as_posix() + "/"
    if any(not p.startswith(prefix + "independent-review") for p in changed):
        raise workers.WorkerError("review harness modified candidate content")
    if current_head() != job["head"]:
        return {"status": "discarded", "reports": reports}
    # Git commits contain only allowlisted review evidence created by the existing runner.
    workers._git(checkout, "add", "--", str(change / "independent-review-request.json"),
                 str(change / "independent-reviews"))
    if workers._git(checkout, "diff", "--cached", "--name-only").strip():
        workers._git(checkout, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                     "commit", "-m", "Record independent review evidence")
    head = workers._git(checkout, "rev-parse", "HEAD").strip()
    if head != job["head"]:
        harness = workers.prepare_harness(source_repo, checkout, checkout.parent, head)
        paths = workers._git(harness, "diff", "--name-only", job["head"], head).splitlines()
        if any(not p.startswith(prefix + "independent-review") for p in paths):
            raise workers.WorkerError("review result includes non-evidence paths")
        if before_push is not None:
            before_push(harness, head)
        if not claim_current():
            return {"status": "discarded"}
        workers.push_validated(harness, branch, job["head"], head, runner=runner, env=push_env)
    return {"status": "reviewed", "pushed_head": head, "reports": reports, "rejected": rejected}


def run_claimed(root: Path, repo: str, candidate: dict, job: dict, *, source_repo: str,
                branch: str, allowed_paths, llm_command, current_head, post_result,
                workdir: str, adapter=queue, runner=None, launcher=None, home_files=(), worker="worker",
                claim_current=None) -> dict:
    """Execute and advance one claimed exact-head job, without the developer."""
    import subprocess

    kind = job["kind"]
    if kind not in {"review", "repair"}:
        raise workers.WorkerError(f"no review-gate executor for {kind}")
    identity = job["task_identity"]
    if claim_current is None:
        def claim_current():
            comments = adapter._comments(root, repo, job["number"])
            return workers.i_won(job, worker, comments, trusted_apps=adapter.trusted_apps(root),
                                 trusted_writers=adapter.trusted_writers(
                                     root, comments, (workers.CLAIM_PREFIX,), repo=repo))
    if not claim_current():
        return {"status": "discarded"}
    observed = adapter._derive(root, adapter._pr(root, repo, job["number"]),
                               adapter._comments(root, repo, job["number"]))
    if workers.build_job(observed) != job:
        return {"status": "discarded"}
    running = adapter._transition(root, repo, job["number"], kind + "ing" if kind == "repair" else "reviewing",
                                  job["head"], task_identity=identity, inherit_identity=False,
                                  next_job={k: v for k, v in job.items() if k != "number"})
    if running is None:
        return {"status": "discarded"}
    if kind == "repair" and running["attempts"].get("repair", 0) > MAX_ROUNDS:
        adapter._transition(root, repo, job["number"], "blocked-escalation", job["head"],
                            task_identity=identity, red_gate={"name": "repair", "evidence": "rounds exhausted"})
        return {"status": "blocked-escalation"}
    if kind == "review" and reusable(root, running.get("gates", {}).get("review"), identity):
        reports = running["gates"]["review"]["evidence"]
        if not claim_current():
            return {"status": "discarded"}
        complete_review(root, repo, running, reports, job["head"], adapter=adapter)
        post_result(workers.result_body(job, worker, "reused-review"))
        return {"status": "reused", "pushed_head": job["head"]}
    runner = runner or subprocess.run

    from independent_review_runner import settings

    review_config = settings(root)
    review_config = {k: v for k, v in review_config.items() if k not in {"provider", "providers"}}
    review_config["providers"] = job.get("providers", [job.get("provider", "unresolved-originating-task-route")])

    def before_push(harness, head):
        if not claim_current():
            return
        workers._git(harness, "checkout", "--detach", head)
        fresh = task_identity(harness, identity["change"])
        post_result(workers.result_body(job, worker, "validated-push", head, task_identity=fresh))

    def review_handler(checkout):
        workers.scratch_home(Path(workdir), home_files)
        return execute_review(checkout, job, source_repo=source_repo, branch=branch,
                              current_head=current_head, runner=runner, launcher=launcher,
                              review_config=review_config, before_push=before_push, claim_current=claim_current)

    if kind == "repair":
        import shlex

        command = shlex.split(llm_command) if isinstance(llm_command, str) else list(llm_command or [])
        if not command or not allowed_paths:
            raise workers.WorkerError("repair needs a configured writer command and bounded allowed paths")
        prompt = ("Repair the material findings in this exact candidate handoff. Commit the bounded fixes. "
                  "Do not edit workflow or lifecycle evidence files. If rejecting a material finding is necessary, "
                  "make no changes and return JSON {\"reject_material\": true}; a human must decide. "
                  "Handoff and findings: " + json.dumps(repair_brief(running), sort_keys=True))
        llm_command = [*command, prompt]
    outcome = workers.execute_job(job, source_repo=source_repo, branch=branch, allowed_paths=allowed_paths,
                                  llm_command=llm_command or [], current_head=current_head, post_result=post_result,
                                  workdir=workdir, runner=runner, home_files=home_files, worker=worker,
                                  review_handler=review_handler if kind == "review" else None, before_push=before_push,
                                  claim_current=claim_current)
    if outcome["status"] == "discarded":
        return outcome
    head = outcome.get("pushed_head") or job["head"]
    if current_head() != head or not claim_current():
        return {**outcome, "status": "discarded"}
    if head != job["head"]:
        adapter._comment(root, repo, job["number"], {"kind": "update", "previous": job["head"],
                                                   "head": head, "worker_job": workers.job_id(job)})
    if kind == "review" and outcome["status"] == "reviewed":
        complete_review(root, repo, running, outcome["reports"], head,
                        rejected=outcome.get("rejected", False), adapter=adapter)
    elif kind == "repair" and outcome["status"] == "pushed":
        harness = Path(workdir) / "harness"
        workers._git(harness, "checkout", "--detach", head)
        fresh = task_identity(harness, identity["change"])
        # Every changed identity must repeat review and checks; retain only proven gates.
        gates = {name: gate for name, gate in running["gates"].items() if reusable(harness, gate, fresh)}
        offer(root, repo, job["number"], head, fresh, "review", gates=gates,
              providers=job.get("providers", ["unresolved-originating-task-route"]), adapter=adapter)
    else:
        adapter._transition(root, repo, job["number"], "blocked-escalation", head,
                            task_identity=identity, red_gate={"name": kind, "evidence": outcome})
    return outcome
