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
    from requirement_child_context import context_path
    context = context_path(root, change)
    contribution = json.loads(context.read_text()).get("contribution") if context.is_file() else None
    proof = review_content_identity(root, change, contribution["head"] if contribution else "origin/main")
    if proof is None:
        raise workers.WorkerError("cannot prove candidate task-content identity")
    from requirement_child_context import context_path
    path = context_path(root, change)
    contribution = json.loads(path.read_text()).get("contribution") if path.is_file() else None
    if contribution:
        context = json.loads(path.read_text())
        requirement, source = context["requirement"], context["source_issue"]
        from managed_task import read_provenance
        from requirement_integration import _public_requirement
        import private_lineage
        provenance = read_provenance(root / "openspec/changes" / change) or {}
        if private_lineage.enabled(root):
            requirement = _public_requirement(root, requirement)
            source = provenance.get("private_lineage_handle")
            if not source:
                raise workers.WorkerError("private contribution lacks authorized public lineage")
        return {"kind": "contribution", "change": change, "task_content": proof,
                "requirement": requirement, "source_issue": source,
                **({"work_identity": provenance["work_identity"]} if provenance.get("work_identity") else {}),
                "target_branch": contribution["target_branch"], "contribution_base": contribution["head"]}
    return {"change": change, "task_content": proof}


def reusable(root: Path, gate: dict | None, identity: dict) -> bool:
    return (isinstance(gate, dict) and gate.get("result") == "passed"
            and isinstance(gate.get("identity"), dict)
            and all(gate["identity"].get(k) == identity.get(k) for k in
                    ("change", "kind", "requirement", "source_issue", "work_identity", "contribution_base", "target_branch", "children"))
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
    if state == "blocked-retryable":
        limitation = next((str(report.get("limitation")) for report in reports.values()
                           if isinstance(report, dict) and report.get("limitation")), "the unavailable review report states no limitation")
        red = {**red, "cause": "provider-unavailable", "providers": providers, "limitation": limitation[:500]}
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
    from requirement_composition import run_child_review
    from independent_review import PERSPECTIVES, _validate_report, read_dispositions, resolve_change

    if job["task_identity"].get("kind") == "requirement-composition":
        from requirement_composition import execute_composition_review
        return execute_composition_review(checkout, job, source_repo=source_repo, branch=branch,
                                          current_head=current_head, runner=runner, launcher=launcher,
                                          review_config=review_config, before_push=before_push,
                                          claim_current=claim_current, push_env=push_env)
    checkout = checkout.resolve()
    identity = job["task_identity"]
    # A finalized candidate that returns to review (integration repair changed its content) is reviewed
    # against its archived artifacts; the active directory no longer exists.
    change = resolve_change(checkout, identity["change"])
    actual = refresh_identity(checkout, identity)
    if actual != identity:
        raise workers.WorkerError("review checkout does not match the published task identity")
    if launcher is None:
        from independent_review_runner import subprocess_launcher
        import os

        clean = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
        launcher = lambda argv, cwd, timeout: subprocess_launcher(argv, cwd, timeout, env=clean)
    reports = run_child_review(checkout, change, launcher=launcher, config=review_config,
                               base_ref=identity.get("contribution_base", "origin/main"))
    request = json.loads((change / "independent-review-request.json").read_text())
    if set(reports) != set(PERSPECTIVES) or any(
            _validate_report(reports[p], request, p, required=True) for p in PERSPECTIVES):
        raise workers.WorkerError("review evidence does not prove both independent perspectives")
    contexts = [reports[p]["reviewer"]["context_id"] for p in PERSPECTIVES]
    if len(set(contexts)) != len(contexts):
        raise workers.WorkerError("review perspectives reused the same context")
    rejected = current_rejections(reports, read_dispositions(change))
    if current_head() != job["head"]:
        return {"status": "discarded", "reports": reports}
    prefix = change.relative_to(checkout).as_posix() + "/"
    # The reviewer's checkout is data only: its files are imported into a harness-owned clone and every
    # git command below runs there without credentials, never against configuration the reviewer could plant.
    harness = workers.prepare_checkout(source_repo, str(checkout.parent), "harness", job["head"])
    workers.import_worktree(checkout, harness)
    evidence = [prefix + "independent-review-request.json", prefix + "independent-reviews"]
    touched = [p for p in workers.harness_git(harness, "diff", "--name-only", "-z").split("\0") if p]
    if any(not p.startswith(prefix + "independent-review") for p in touched):
        raise workers.WorkerError("review harness modified candidate content")
    # Git commits contain only allowlisted review evidence created by the existing runner.
    existing = [p for p in evidence if (harness / p).exists()]
    if existing:
        workers.harness_git(harness, "add", "--", *existing)
    head = job["head"]
    if workers.harness_git(harness, "diff", "--cached", "--name-only").strip():
        workers.harness_git(harness, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                            "commit", "-m", "Record independent review evidence")
        head = workers.harness_git(harness, "rev-parse", "HEAD").strip()
    if head != job["head"]:
        if before_push is not None:
            before_push(harness, head)
        if not claim_current():
            return {"status": "discarded"}
        workers.push_validated(harness, branch, job["head"], head, runner=runner, env=push_env)
    return {"status": "reviewed", "pushed_head": head, "reports": reports, "rejected": rejected}


def run_claimed(root: Path, repo: str, candidate: dict, job: dict, *, source_repo: str,
                branch: str, allowed_paths, llm_command, current_head, post_result,
                workdir: str, adapter=queue, runner=None, launcher=None, home_files=(), worker="worker",
                claim_current=None, review_ready=None, repair_runtime_check=None) -> dict:
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
    if review_ready is not None:
        # A filtering worker runs only the ready subset, in the job's order.
        review_config["providers"] = [name for name in review_config["providers"] if name in review_ready]

    def before_push(harness, head):
        if not claim_current():
            return
        workers._git(harness, "checkout", "--detach", head)
        fresh = refresh_identity(harness, identity)
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
                                  claim_current=claim_current,
                                  runtime_check=repair_runtime_check if kind == "repair" else None)
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
        fresh = refresh_identity(harness, identity)
        # Every changed identity must repeat review and checks; retain only proven gates.
        gates = {name: gate for name, gate in running["gates"].items() if reusable(harness, gate, fresh)}
        offer(root, repo, job["number"], head, fresh, "review", gates=gates,
              providers=job.get("providers", ["unresolved-originating-task-route"]),
              set_attempts={"repair-unavailable": 0} if running["attempts"].get("repair-unavailable") else None,
              adapter=adapter)
    elif kind == "repair" and outcome["status"] == "unavailable":
        retry_unavailable(root, repo, running, job, outcome["outcome"], adapter=adapter)
    else:
        adapter._transition(root, repo, job["number"], "blocked-escalation", head,
                            task_identity=identity,
                            red_gate={"name": kind, "evidence": outcome, "providers": job.get("providers")})
    return outcome


def retry_unavailable(root: Path, repo: str, running: dict, job: dict, limitation: str, *, adapter=queue) -> dict | None:
    """An unavailable repair runtime is retryable on the same round; only the unavailable streak is bounded."""
    from datetime import datetime, timezone
    from lifecycle_workers import job_record

    identity, attempts, kind = job["task_identity"], running.get("attempts", {}), job["kind"]
    streak = attempts.get(f"{kind}-unavailable", 0) + 1
    providers = job.get("providers")
    gate = {"result": "failed", "identity": identity,
            "evidence": {"cause": "provider-unavailable", "providers": providers, "limitation": limitation[:500]}}
    set_attempts, next_job = {f"{kind}-unavailable": streak}, None
    if streak < MAX_ROUNDS:
        seq = attempts.get("reoffers", 0) + 1
        set_attempts["reoffers"] = seq
        reoffer = {"seq": seq, "action": "retry-unavailable", "from": providers, "to": providers,
                   "reason": "provider-unavailable", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        next_job = job_record(kind, job["head"], identity, job["attempt"], providers=providers, reoffer=reoffer)
    return adapter._transition(root, repo, job["number"], "blocked-retryable", job["head"], task_identity=identity,
                               inherit_identity=False, gates={**running.get("gates", {}), kind: gate},
                               red_gate=running.get("red_gate"), set_attempts=set_attempts, next_job=next_job)


OPERATIONAL_REPAIR_OUTCOMES = frozenset({"failed", "rejected", "no-change"})
ACTIONS = ("switch-provider", "resume")


def _repair_status(red_gate: dict) -> str:
    evidence = red_gate.get("evidence")
    return str(evidence.get("status") if isinstance(evidence, dict) else evidence).split(":")[0]


def reoffer(root: Path, repo: str, number: int, *, action: str, providers, reason: str, adapter=queue) -> dict:
    """Re-offer the open review or repair job of a candidate, optionally on other providers.

    One appended record keeps identity, gates, findings and every attempt counter, so the same round is
    offered again and no budget is spent; the distinct job id comes from the ``reoffers`` sequence.
    """
    from datetime import datetime, timezone
    from independent_review_runner import PROVIDERS
    from lifecycle_workers import job_record

    if action not in ACTIONS:
        raise ValueError(f"unknown re-offer action {action!r}")
    if not reason or not reason.strip():
        raise adapter.QueueError("a re-offer needs the operator's reason")
    pr = adapter._pr(root, repo, number)
    if pr.get("state") != "open" or pr.get("merged"):
        raise adapter.QueueError(f"PR #{number} is not open")
    head = pr["head"]["sha"]
    comments = adapter._comments(root, repo, number)
    if adapter._latest(root, number, comments, head) is None:
        raise adapter.QueueError(f"PR #{number} has no coordinator record for its current head")
    candidate = adapter._derive(root, pr, comments)
    state, identity = candidate["state"], candidate.get("task_identity")
    current_job = candidate.get("next_job") if isinstance(candidate.get("next_job"), dict) else {}
    red = candidate.get("red_gate") or {}
    pending = {"review-pending": "review", "reviewing": "review", "repair-pending": "repair", "repairing": "repair"}
    if state in pending:
        if action == "resume":
            raise adapter.QueueError(f"PR #{number} is {state}; use switch-provider to change its provider")
        kind = pending[state]
    elif state == "blocked-retryable" and adapter.retry_job_kind(candidate):
        kind = adapter.retry_job_kind(candidate)
    elif state == "blocked-escalation" and red.get("name") in {"repair", "review"} and action == "resume":
        if red["name"] == "review" or _repair_status(red) not in OPERATIONAL_REPAIR_OUTCOMES:
            reason_ = "review" if red["name"] == "review" else _repair_status(red)
            raise adapter.QueueError(
                f"PR #{number} is escalated for a finding-level reason ({reason_}); resume does not decide it: "
                "push a fix, record a disposition for the finding, or close the PR")
        kind = "repair"
    else:
        raise adapter.QueueError(f"PR #{number} is {state}; {action} applies only to an unfinished review or repair job"
                                 + (" (resume covers operational repair escalations)" if state == "blocked-escalation" else ""))
    from lifecycle_workers import CLAIM_PREFIX, build_job, winning_claim
    job = build_job(candidate)
    if job is not None:
        claim = winning_claim(job, comments, trusted_apps=adapter.trusted_apps(root),
                              trusted_writers=adapter.trusted_writers(root, comments, (CLAIM_PREFIX,), repo=repo))
        if claim is not None:
            raise adapter.QueueError(f"PR #{number} job is claimed by {claim['worker']} until {claim['expires_at']}; "
                                     "wait for the claim to expire or finish")
    unavailable = (candidate.get("gates", {}).get("repair") or {}).get("evidence")
    previous = (current_job.get("providers") or red.get("providers")
                or (unavailable.get("providers") if isinstance(unavailable, dict) else None) or [])
    if providers is None:
        if not previous:
            raise adapter.QueueError(f"PR #{number} records no provider for this job; pass --provider")
        providers = list(previous)
    providers = list(providers)
    if not providers or len(set(providers)) != len(providers) or any(name not in PROVIDERS for name in providers):
        raise adapter.QueueError(f"providers must be a nonempty list of distinct values from {', '.join(PROVIDERS)}")
    if action == "switch-provider" and state in pending and providers == previous:
        return {"state": state, "number": number, "changed": False, "providers": providers}
    attempts = candidate.get("attempts", {})
    gates = candidate.get("gates", {})
    if kind == "repair":
        if red.get("name") not in {None, "repair"} and state != "blocked-escalation":
            restored = red
        else:
            origin = next((name for name in ("review", "required-checks") if gates.get(name, {}).get("result") == "failed"), None)
            if origin is None:
                raise adapter.QueueError(f"PR #{number} no longer carries the failed review or check evidence to repair")
            restored = {"name": origin, "identity": identity, "evidence": gates[origin]["evidence"]}
    else:
        restored = None
    seq = attempts.get("reoffers", 0) + 1
    event = {"seq": seq, "action": action, "from": previous, "to": providers, "reason": reason.strip()[:300],
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    record = adapter._transition(
        root, repo, number, f"{kind}-pending", head, task_identity=identity, inherit_identity=False, red_gate=restored,
        set_attempts={"reoffers": seq, f"{kind}-unavailable": 0},
        next_job=job_record(kind, head, identity, attempts.get(kind, 0), providers=providers, reoffer=event))
    if record is None:
        raise adapter.QueueError(f"PR #{number} head moved; rerun")
    return {"state": record["state"], "number": number, "changed": True, "job": record["next_job"]}


def refresh_identity(root: Path, identity: dict) -> dict:
    if identity.get("kind") == "requirement-composition":
        from requirement_composition import composition_identity, candidate_manifest
        return composition_identity(root, candidate_manifest(root, identity["requirement"]))
    if identity.get("kind") == "contribution":
        proof = review_content_identity(root, identity["change"], identity["contribution_base"])
        if proof is None:
            raise workers.WorkerError("cannot prove contribution content")
        return {**identity, "task_content": proof}
    return task_identity(root, identity["change"])
