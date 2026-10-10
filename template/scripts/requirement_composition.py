"""Composition-only review and one archive finalization for reviewed contributions.

Reviewer prompts reuse the established perspectives and launcher. All candidate
Git operations after either LLM launch take place in a fresh harness clone.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import lifecycle_workers as workers
import requirement_contributions as contributions
import requirement_integration as integration
from task_content_identity import composition_content_identity, equivalent_proofs, _canonical_path


def candidate_manifest(checkout: Path, requirement: str) -> dict:
    return contributions.read_manifest(checkout, requirement)


def evidence_directory(requirement: str) -> Path:
    return Path("dev-platform/requirement-evidence") / integration._candidate_slug(requirement)


def validate_children(checkout: Path, manifest: dict) -> None:
    contributions.validate(manifest)
    if not integration.manifest_complete(manifest):
        raise contributions.ContributionError("composition requires every mandatory contribution exactly once")
    for child in manifest["children"]:
        identity = child["task_identity"]
        contributions.require_gates({"head": child["head"], "task_identity": identity, "gates": child["gates"]})
        if integration._digest(child["gates"]) != child["reviewed_evidence_digest"]:
            raise contributions.ContributionError("child reviewed evidence digest changed")
        workers.harness_git(checkout, "merge-base", "--is-ancestor", child["contribution_base"], child["head"])
        workers.harness_git(checkout, "merge-base", "--is-ancestor", child["head"], child["integrated_head"])
        workers.harness_git(checkout, "merge-base", "--is-ancestor", child["integrated_head"], "HEAD")
        # Bind the reviewed identity to its preserved contribution head. Later
        # contributions and composition repairs may extend the same files.
        with tempfile.TemporaryDirectory(prefix="composition-child-") as temporary:
            # The harness contract comes from the trusted composition checkout: a child
            # head reviewed before the public source contract existed carries none.
            child_checkout = workers.prepare_checkout(str(checkout), temporary, "harness", child["head"],
                                                      contract_from=checkout / ".dev-platform.toml")
            from task_content_identity import review_content_identity
            actual = review_content_identity(child_checkout, child["change"], child["contribution_base"])
            if actual != identity["task_content"]:
                raise contributions.ContributionError(f"child reviewed identity changed: {child['change']}")
        tree = workers.harness_git(checkout, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        aliases = {_canonical_path(raw, child["change"]): raw for raw in tree}
        # Evidence is carried byte for byte from each child's reviewed boundary.
        for gate, filename in (("selected-checks", "automated-checks.json"), ("semantic-verification", "verification.md")):
            path = aliases.get(f"openspec/changes/{child['change']}/{filename}")
            reference = child["gates"][gate]["evidence"]
            if gate == "selected-checks" and reference.get("harness_executed"):
                workers.harness_git(checkout, "merge-base", "--is-ancestor", reference["head"], child["head"])
                continue
            observed = workers.harness_git(checkout, "show", f"HEAD:{path}").encode() if path else b""
            if not path or hashlib.sha256(observed).hexdigest() != reference.get("sha256"):
                raise contributions.ContributionError(f"child {gate} receipt changed since review")


def composition_identity(checkout: Path, manifest: dict) -> dict:
    validate_children(checkout, manifest)
    proof = composition_content_identity(checkout, manifest["expected_changes"], manifest["base"])
    if proof is None:
        raise contributions.ContributionError("cannot prove composition task content")
    return {"kind": "requirement-composition", "change": integration._candidate_slug(manifest["requirement"]),
            "requirement": manifest["requirement"], "task_content": proof,
            "children": [{"change": c["change"], "head": c["head"], "identity": c["task_identity"],
                          "reviewed_evidence_digest": c["reviewed_evidence_digest"]} for c in manifest["children"]]}


def prepare_request(checkout: Path, manifest: dict, outcome: str) -> dict:
    from independent_review import PERSPECTIVES, SCHEMA_VERSION
    from _platform_common import utc_now
    import uuid

    identity = composition_identity(checkout, manifest)
    head = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
    objective = ("Review only cross-child contract compatibility, duplicated or conflicting behavior, and the Requirement outcome. "
                 "Do not fully re-review unchanged child implementations: their reviewed content identities have been proven. "
                 f"Requirement outcome: {outcome}\nReviewed children: " + json.dumps(identity["children"], sort_keys=True))
    return {"schema_version": SCHEMA_VERSION, "request_id": str(uuid.uuid4()), "prepared_at": utc_now(),
            "change": identity["change"], "kind": "requirement-composition", "requirement": manifest["requirement"],
            "candidate": {"base_ref": manifest["base"], "base_head": manifest["base"], "candidate_head": head,
                          "diff_sha256": hashlib.sha256(workers.harness_git(checkout, "diff", "--binary", "--no-ext-diff", f"{manifest['base']}...HEAD").encode()).hexdigest()},
            "task_content": identity["task_content"], "children": identity["children"],
            "fresh_context_required": True,
            "perspectives": {p: {"objective": objective, "paths": ["AGENTS.md"]} for p in PERSPECTIVES}}


def validate_request(request: dict, identity: dict) -> None:
    from independent_review import _validate_request
    if (_validate_request(request) or request.get("kind") != "requirement-composition"
            or request.get("requirement") != identity["requirement"]
            or request.get("children") != identity["children"]
            or request.get("task_content", {}).get("digest") != identity["task_content"]["digest"]):
        raise workers.WorkerError("composition review request is stale or malformed")


def review_diff_paths(checkout: Path, manifest: dict, identity: dict) -> list[str]:
    """Resolve logical identity paths against both Git trees, including deleted artifacts."""
    aliases = {}
    for ref in (manifest["base"], "HEAD"):
        for raw in workers.harness_git(checkout, "ls-tree", "-r", "--name-only", ref).splitlines():
            canonical = raw
            for change in manifest["expected_changes"]:
                canonical = _canonical_path(canonical, change)
            aliases.setdefault(canonical, set()).add(raw)
    paths = []
    for canonical in identity["task_content"]["paths"]:
        if canonical not in aliases:
            raise workers.WorkerError(f"composition review path is absent from both Git trees: {canonical}")
        paths.extend(sorted(aliases[canonical]))
    return paths


def private_lineage_requirement(manifest: dict) -> bool:
    """A Requirement published only through its opaque private-lineage handle."""
    return not integration.ISSUE_RE.fullmatch(manifest["requirement"])


def requirement_outcome(body: str) -> str:
    """The `## Outcome` section of a Requirement body; a body without one fails."""
    lines = body.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Outcome") + 1
    except StopIteration:
        raise workers.WorkerError("Requirement body has no `## Outcome` section") from None
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    outcome = "\n".join(lines[start:end]).strip()
    if not outcome:
        raise workers.WorkerError("Requirement `## Outcome` section is empty")
    return outcome


def require_no_private_references(trusted_root: Path, evidence: list[Path]) -> None:
    """Fail before committing composition evidence that names a private Backlog Issue directly."""
    import importlib.util
    from _platform_common import read_platform_config

    guard_path = trusted_root / "scripts" / "check_private_backlog_refs.py"
    if not guard_path.is_file():
        raise workers.WorkerError("private lineage needs scripts/check_private_backlog_refs.py in the trusted root")
    spec = importlib.util.spec_from_file_location("check_private_backlog_refs", guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    repository = read_platform_config(trusted_root).get("development_backlog", {}).get("repository")
    if not repository:
        raise workers.WorkerError("private-reference check needs the configured Backlog repository")
    pattern = guard.private_reference_pattern(repository)
    leaking = sorted(path.name for path in evidence if pattern.search(path.read_text(encoding="utf-8")))
    if leaking:
        raise workers.WorkerError("composition evidence would publish a direct private Backlog reference in "
                                  + ", ".join(leaking))


def execute_composition_review(checkout: Path, job: dict, *, source_repo: str, branch: str, current_head,
                               trusted_root: Path, runner=subprocess.run, launcher=None, review_config=None,
                               before_push=None, claim_current=lambda: True, push_env=None) -> dict:
    from independent_review import PERSPECTIVES, _validate_report
    import independent_review_runner as reviewer

    identity = job["task_identity"]
    manifest = candidate_manifest(checkout, identity["requirement"])
    actual = composition_identity(checkout, manifest)
    if actual != identity:
        raise workers.WorkerError("composition content differs from the offered job")
    # The Requirement outcome is obtained by trusted coordinator I/O before the LLM step: the
    # disposable checkout carries only the public contract and must know nothing private.
    import managed_task
    private = private_lineage_requirement(manifest)
    issue = managed_task.fetch_issue(trusted_root, *managed_task.issue_ref(contributions.private_requirement(trusted_root, manifest)))
    body = str(issue.get("body") or "")
    # A private Requirement contributes only its outcome; its body also lists private child Issues.
    request = prepare_request(checkout, manifest, requirement_outcome(body) if private else body)
    validate_request(request, identity)
    config = reviewer.settings(checkout) if review_config is None else review_config
    clean = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
    launcher = launcher or (lambda argv, cwd, timeout: reviewer.subprocess_launcher(argv, cwd, timeout, env=clean))
    diff, error = reviewer.candidate_diff(checkout, manifest["base"], review_diff_paths(checkout, manifest, identity))
    reports = {}
    snapshot = workers.tree_snapshot(checkout)
    readiness = reviewer.preflight(checkout, config=config, launcher=launcher)
    with tempfile.TemporaryDirectory(prefix="composition-review-") as temporary:
        scratch = Path(temporary)
        (scratch / "findings-schema.json").write_text(json.dumps(reviewer.FINDINGS_SCHEMA), encoding="utf-8")
        diff_path = scratch / "candidate.diff"
        diff_path.write_text(diff, encoding="utf-8")
        for perspective in PERSPECTIVES:
            reports[perspective] = reviewer.run_perspective(
                checkout, request, perspective, provider=readiness["provider"], model=readiness["model"],
                binary=readiness["binary"], limitation=error or (None if readiness["ready"] else readiness["limitation"]),
                launcher=launcher, timeout=reviewer.timeout_seconds(config), scratch=scratch, diff_path=diff_path,
                watched=[])
    # No Git in the reviewer checkout from this point onward.
    if workers.tree_snapshot(checkout) != snapshot:
        raise workers.WorkerError("composition reviewer modified the checkout")
    if any(_validate_report(reports[p], request, p, required=True) for p in PERSPECTIVES):
        raise workers.WorkerError("composition reports do not prove independent perspectives")
    if len({reports[p]["reviewer"]["context_id"] for p in PERSPECTIVES}) != len(PERSPECTIVES):
        raise workers.WorkerError("composition reviewers reused a context")
    if current_head() != job["head"] or not claim_current():
        return {"status": "discarded"}
    harness = workers.prepare_checkout(source_repo, str(checkout.parent), "harness", job["head"])
    directory = harness / evidence_directory(identity["requirement"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "request.json").write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for perspective, report in reports.items():
        (directory / f"{perspective}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        require_no_private_references(trusted_root, sorted(directory.glob("*.json")))
    workers.harness_git(harness, "add", "--", str(directory.relative_to(harness)))
    workers.harness_git(harness, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                        "commit", "-m", "Record Requirement composition review")
    head = workers.harness_git(harness, "rev-parse", "HEAD").strip()
    if before_push:
        before_push(harness, head)
    if current_head() != job["head"] or not claim_current():
        return {"status": "discarded"}
    contributions.push_fast_forward(harness, branch, job["head"], head, runner=runner)
    return {"status": "reviewed", "pushed_head": head, "reports": reports, "rejected": False}


def require_final_gates(checkout: Path, manifest: dict, candidate: dict, head: str) -> None:
    """All publication entrypoints use the same fail-closed readiness predicate."""
    from pr_review_gate import reusable

    identity = composition_identity(checkout, manifest)
    if candidate.get("head") != head or candidate.get("task_identity") != identity:
        raise contributions.ContributionError("Requirement final gates are not bound to exact head")
    for name in ("review", "finalization", "requirement-retrospective", "full-checks"):
        gate = candidate.get("gates", {}).get(name)
        if not reusable(checkout, gate, identity):
            raise contributions.ContributionError(f"Requirement readiness lacks {name}")
        if name == "full-checks" and gate.get("evidence", {}).get("head") != head:
            raise contributions.ContributionError("Requirement full checks are not on exact final head")
    if any((checkout / "openspec/changes" / c).exists() for c in manifest["expected_changes"]):
        raise contributions.ContributionError("Requirement finalization has not archived all children")


def composition_providers(root: Path, manifest: dict) -> list[str]:
    """Resolve mandatory child routes, never the integration checkout's current task."""
    from independent_review_runner import settings, PROVIDERS
    import model_routing

    config = settings(root)
    if "providers" in config:
        providers = config["providers"]
    elif "provider" in config:
        providers = [config["provider"]]
    else:
        private = contributions.private_manifest(root, manifest)
        providers = list(dict.fromkeys(model_routing.read_durable_route(
            root, child["source_issue"], child["change"])[0].provider for child in private["children"]))
    if (not isinstance(providers, list) or not providers
            or any(p not in PROVIDERS for p in providers) or len(set(providers)) != len(providers)):
        raise contributions.ContributionError("composition review requires explicit valid child or configured providers")
    return providers


def publish_composition(root: Path, repo: str, manifest: dict, head: str, *, adapter=None, source_repo=None) -> dict:
    """Maintain one draft PR; completeness offers composition review, never readiness."""
    if adapter is None:
        import publication_queue as adapter
    from project_publish import ensure_pr
    from publication_state import find_exact_head_pr
    from _platform_common import github_cli_env

    env = getattr(adapter, "github_cli_env", github_cli_env)(root)
    if env is None:
        raise contributions.ContributionError("Requirement draft publication needs GitHub authentication")
    branch = manifest["integration_branch"]
    lookup = getattr(adapter, "find_exact_head_pr", find_exact_head_pr)(root, env, branch, "main", head)
    if not lookup.available:
        raise contributions.ContributionError("Requirement exact PR state unavailable")
    if lookup.stale_open is not None:
        raise contributions.ContributionError("Requirement PR head differs from the observed integration branch; retry fresh observation")
    pr = getattr(adapter, "ensure_pr", ensure_pr)(root, env, branch, "main", f"Compose {manifest['work_identity']}",
                   f"Reviewed contributions for {manifest['work_identity']}", head, lookup=lookup, draft=True)
    if pr.already_merged:
        return reconcile_composition(root, repo, manifest, head, pr.number, adapter=adapter, source_repo=source_repo)
    if integration.manifest_complete(manifest) and not pr.already_merged:
        current = adapter._derive(root, adapter._pr(root, repo, pr.number), adapter._comments(root, repo, pr.number))
        with tempfile.TemporaryDirectory(prefix="composition-offer-") as temporary:
            checkout = workers.prepare_checkout(source_repo or f"https://github.com/{repo}.git", temporary, "harness", head)
            identity = composition_identity(checkout, manifest)
            from pr_review_gate import reusable
            finalized = reusable(checkout, current.get("gates", {}).get("review"), identity) and reusable(
                checkout, current.get("gates", {}).get("finalization"), identity)
        if finalized:
            return advance_final_publication(root, repo, manifest, head, pr.number, adapter=adapter, source_repo=source_repo)
        if (current.get("task_identity") == identity and current.get("state") == "finalize-pending"):
            from pr_review_gate import offer
            offer(root, repo, pr.number, head, identity, "finalize", gates=current.get("gates", {}), adapter=adapter)
        elif current.get("task_identity") != identity:
            from pr_review_gate import offer
            gate = {"result": "passed", "identity": identity, "evidence": {"children": identity["children"]}}
            offer(root, repo, pr.number, head, identity, "review",
                  gates={"selected-checks": gate, "semantic-verification": gate},
                  providers=composition_providers(root, manifest), adapter=adapter)
    return {"status": "draft-published", "branch": branch, "head": head, "pr": pr.url}


def validate_composition_reports(checkout: Path, identity: dict) -> dict:
    from independent_review import PERSPECTIVES, _validate_report

    directory = checkout / evidence_directory(identity["requirement"])
    try:
        request = json.loads((directory / "request.json").read_text())
        reports = {p: json.loads((directory / f"{p}.json").read_text()) for p in PERSPECTIVES}
    except (OSError, ValueError) as exc:
        raise workers.WorkerError("composition review evidence unavailable") from exc
    validate_request(request, identity)
    if (any(_validate_report(reports[p], request, p, required=True) for p in PERSPECTIVES)
            or any(r.get("availability") != "available" for r in reports.values())
            or any(f.get("severity") == "material" for r in reports.values() for f in r.get("findings", []))
            or len({r["reviewer"]["context_id"] for r in reports.values()}) != len(PERSPECTIVES)):
        raise workers.WorkerError("composition review did not pass both independent perspectives")
    return reports


def require_archive_evidence(checkout: Path, change: str, requirement: str) -> None:
    manifest = candidate_manifest(checkout, requirement)
    if change not in manifest["expected_changes"]:
        raise workers.WorkerError("archive change is outside the Requirement")
    identity = composition_identity(checkout, manifest)
    validate_composition_reports(checkout, identity)


def execute_composition_finalize(checkout: Path, job: dict, gates: dict, *, source_repo: str, branch: str,
                                 current_head, runner=subprocess.run, archiver=None, push_env=None,
                                 before_push=None, claim_current=lambda: True, checks_runner=None) -> dict:
    from post_review_finalization import trusted_archiver, validate_finalization_paths
    from pr_review_gate import reusable

    identity = job["task_identity"]
    manifest = candidate_manifest(checkout, identity["requirement"])
    actual = composition_identity(checkout, manifest)
    if not equivalent_proofs(checkout, identity["task_content"], actual["task_content"]):
        return {"status": "changed", "identity": actual}
    if not reusable(checkout, gates.get("review"), actual):
        raise workers.WorkerError("composition finalization lacks content-bound review")
    validate_composition_reports(checkout, actual)
    env = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
    env["DEV_PLATFORM_COMPOSITION_FINALIZATION"] = identity["requirement"]
    # Preserve contribution integration order; shared capability deltas are applied once, in order.
    for child in manifest["children"]:
        name = child["change"]
        if (checkout / "openspec/changes" / name).is_dir():
            (archiver or trusted_archiver)(checkout, name, env)
        else:
            from post_review_finalization import _archive_dir
            if _archive_dir(checkout, name) is None:
                raise workers.WorkerError(f"missing active or archived child: {name}")
    workers.harness_git(checkout, "add", "-A", "--", "openspec")
    leftovers = workers.harness_git(checkout, "diff", "--name-only").strip()
    if leftovers or workers.harness_git(checkout, "ls-files", "--others", "--exclude-standard").strip():
        raise workers.WorkerError("composition archive wrote outside openspec")
    if workers.harness_git(checkout, "diff", "--cached", "--name-only").strip():
        workers.harness_git(checkout, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                            "commit", "-m", "Archive reviewed Requirement contributions")
    head = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
    validate_finalization_paths(checkout, job["head"], head, manifest["expected_changes"])
    fresh = composition_identity(checkout, manifest)
    if not equivalent_proofs(checkout, identity["task_content"], fresh["task_content"]):
        raise workers.WorkerError("composition finalization changed reviewed product content")
    if current_head() != job["head"] or not claim_current():
        return {"status": "discarded"}
    if head != job["head"]:
        if before_push:
            before_push(checkout, head)
        contributions.push_fast_forward(checkout, branch, job["head"], head, runner=runner)
    return {"status": "finalized", "pushed_head": head if head != job["head"] else None,
            "identity": fresh, "gates": {**gates, "finalization": {"result": "passed", "identity": fresh,
                "evidence": {"head": head, "changes": manifest["expected_changes"]}}}}


def advance_final_publication(root: Path, repo: str, manifest: dict, head: str, number: int, *, adapter,
                              source_repo=None, full_checks=None, checkpoint=None, enqueue=True) -> dict:
    """Check the parent retrospective and full final head before readiness and queue admission."""
    from project_publish import _set_pr_draft
    from publication_state import PrRef
    from _platform_common import github_cli_env
    from requirement_retrospective import require_checkpoint, RequirementRetrospectiveError
    from pr_review_gate import reusable

    candidate = adapter._derive(root, adapter._pr(root, repo, number), adapter._comments(root, repo, number))
    with tempfile.TemporaryDirectory(prefix="composition-ready-") as temporary:
        checkout = workers.prepare_checkout(source_repo or f"https://github.com/{repo}.git", temporary, "harness", head)
        identity = composition_identity(checkout, manifest)
        if not all(reusable(checkout, candidate.get("gates", {}).get(g), identity) for g in ("review", "finalization")):
            return {"status": "await-composition-finalization", "head": head}
        retrospective = candidate.get("gates", {}).get("requirement-retrospective")
        if checkpoint is None and not reusable(checkout, retrospective, identity):
            adapter.publish_job(root, repo, number, "retrospective", head, task_identity=identity, phase="pre-merge")
            return {"status": "await-requirement-retrospective", "head": head}
        try:
            receipt = (checkpoint or require_checkpoint)(root, requirement=contributions.private_requirement(root, manifest))
        except RequirementRetrospectiveError:
            adapter.publish_job(root, repo, number, "retrospective", head, task_identity=identity, phase="pre-merge")
            return {"status": "await-requirement-retrospective", "head": head}
        full = candidate.get("gates", {}).get("full-checks", {})
        if full.get("evidence", {}).get("head") != head or not reusable(checkout, full, identity):
            if full_checks is not None:
                full_checks(checkout)
            else:
                # The disposable checkout has only the public contract; the trusted root supplies the registry.
                integration._run_full_checks(checkout, trusted_root=root)
        if adapter._pr(root, repo, number).get("head", {}).get("sha") != head:
            return {"status": "discarded"}
        gates = {**candidate["gates"],
                 "requirement-retrospective": {"result": "passed", "identity": identity, "evidence": receipt},
                 "full-checks": {"result": "passed", "identity": identity, "evidence": {"head": head}}}
        exact = {**candidate, "head": head, "task_identity": identity, "gates": gates}
        require_final_gates(checkout, manifest, exact, head)
        adapter._transition(root, repo, number, "ready", head, task_identity=identity,
                            inherit_identity=False, gates=gates)
    env = getattr(adapter, "github_cli_env", github_cli_env)(root)
    pr = adapter._pr(root, repo, number)
    if pr.get("draft"):
        getattr(adapter, "set_pr_draft", _set_pr_draft)(root, env, PrRef(number=number, url=pr["html_url"]), draft=False)
    if enqueue:
        adapter.admit(root, number, head)
    return {"status": "queued" if enqueue else "ready", "head": head, "number": number}


def run_child_review(checkout: Path, change: Path, *, base_ref: str, launcher, config) -> dict:
    """Use existing reviewers without Git-based postchecks in their writable checkout."""
    import independent_review as review
    import independent_review_runner as reviewer
    from _platform_common import atomic_write_text

    request = review.prepare_request(checkout, change, base_ref)
    paths, _ = review.lifecycle_path_partition(checkout, change, base_ref, request["task_content"]["base"])
    diff, error = reviewer.candidate_diff(checkout, request["task_content"]["base"], paths)
    config = reviewer.settings(checkout) if config is None else config
    clean = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
    launcher = launcher or (lambda argv, cwd, timeout: reviewer.subprocess_launcher(argv, cwd, timeout, env=clean))
    reports = {}
    snapshot = workers.tree_snapshot(checkout)
    readiness = reviewer.preflight(checkout, config=config, launcher=launcher)
    with tempfile.TemporaryDirectory(prefix="contribution-review-") as temporary:
        scratch = Path(temporary)
        (scratch / "findings-schema.json").write_text(json.dumps(reviewer.FINDINGS_SCHEMA), encoding="utf-8")
        diff_path = scratch / "candidate.diff"
        diff_path.write_text(diff, encoding="utf-8")
        for perspective in review.PERSPECTIVES:
            reports[perspective] = reviewer.run_perspective(
                checkout, request, perspective, provider=readiness["provider"], model=readiness["model"],
                binary=readiness["binary"], limitation=error or (None if readiness["ready"] else readiness["limitation"]),
                launcher=launcher, timeout=reviewer.timeout_seconds(config), scratch=scratch, diff_path=diff_path,
                watched=[])
    if workers.tree_snapshot(checkout) != snapshot:
        raise workers.WorkerError("child reviewer modified the checkout")
    for perspective, report in reports.items():
        atomic_write_text(review.report_path(change, perspective), json.dumps(report, indent=2, sort_keys=True) + "\n")
    return reports


def reconcile_composition(root: Path, repo: str, manifest: dict, head: str, number: int, *, adapter, source_repo=None, ops=None) -> dict:
    """Terminal delivery requires exact merged proof and all pre-readiness gates, even on rerun."""
    from _platform_common import read_platform_config
    from integration_state import serialized_integration
    from finish_task import sync_after_remote_pr_merge
    import managed_project_status
    import requirement_terminal

    pr = adapter._pr(root, repo, number)
    if not pr.get("merged") or pr.get("head", {}).get("sha") != head or pr.get("base", {}).get("ref") != "main":
        raise contributions.ContributionError("terminal delivery lacks exact Requirement merge to main")
    candidate = adapter._derive(root, pr, adapter._comments(root, repo, number))
    with tempfile.TemporaryDirectory(prefix="composition-terminal-") as temporary:
        checkout = workers.prepare_checkout(source_repo or f"https://github.com/{repo}.git", temporary, "harness", head)
        require_final_gates(checkout, manifest, candidate, head)
    config = read_platform_config(root)
    with serialized_integration(root, config, 60.0):
        (getattr(ops, "sync", None) or sync_after_remote_pr_merge)(root, root, config, "main")
        exact = contributions.private_manifest(root, manifest)
        integration._verify_parent_links(root, exact)
        for child in exact["children"]:
            (getattr(ops, "reconcile_child", None) or managed_project_status.reconcile)(root, "Done", source_issue=child["source_issue"])
        (getattr(ops, "reconcile_parent", None) or requirement_terminal.reconcile_parent)(
            root, requirement=exact["requirement"], merged_children={c["source_issue"] for c in exact["children"]})
    return {"status": "merged-and-reconciled", "requirement": manifest["requirement"], "head": head, "number": number}


def run_claimed_retrospective(root: Path, repo: str, candidate: dict, job: dict, *, source_repo: str,
                             post_result, worker: str, adapter=None, ops=None, claim_current=None,
                             checkpoint=None, resolve_manifest=None) -> dict:
    """Complete the parent retrospective before readiness, under an exact-head claim."""
    if adapter is None:
        import publication_queue as adapter
    from integration_contour import LifecycleOps, ensure_requirement_checkpoint, JobBlocked
    from pr_review_gate import reusable
    from requirement_retrospective import require_checkpoint, RequirementRetrospectiveError

    number, head, identity = job["number"], job["head"], job["task_identity"]
    if claim_current is None:
        def claim_current():
            comments = adapter._comments(root, repo, number)
            return workers.i_won(job, worker, comments, trusted_apps=adapter.trusted_apps(root),
                                 trusted_writers=adapter.trusted_writers(root, comments, (workers.CLAIM_PREFIX,), repo=repo))
    def current():
        return claim_current() and adapter._pr(root, repo, number).get("head", {}).get("sha") == head
    candidate = adapter._derive(root, adapter._pr(root, repo, number), adapter._comments(root, repo, number))
    if job.get("phase") != "pre-merge" or workers.build_job(candidate) != job or not current():
        return {"status": "discarded"}
    try:
        with tempfile.TemporaryDirectory(prefix="composition-retrospective-") as temporary:
            checkout = workers.prepare_checkout(source_repo, temporary, "harness", head)
            manifest = candidate_manifest(checkout, identity["requirement"])
            if composition_identity(checkout, manifest) != identity:
                raise JobBlocked("Requirement retrospective identity changed")
            if not all(reusable(checkout, candidate.get("gates", {}).get(g), identity)
                       for g in ("review", "finalization")):
                raise JobBlocked("Requirement retrospective requires review and finalization")
            private = (resolve_manifest or contributions.private_manifest)(root, manifest)
            requirement = private["requirement"]
            ensure_requirement_checkpoint(ops or LifecycleOps(), root, requirement,
                                          [c["source_issue"] for c in private["children"]])
            receipt = (checkpoint or require_checkpoint)(root, requirement=requirement)
            if not current():
                return {"status": "discarded"}
            adapter._transition(root, repo, number, "blocked-retryable", head, task_identity=identity,
                                inherit_identity=False, gates={**candidate["gates"], "requirement-retrospective": {
                                    "result": "passed", "identity": identity, "evidence": receipt}})
        outcome = advance_final_publication(root, repo, manifest, head, number, adapter=adapter, source_repo=source_repo)
    except (JobBlocked, workers.WorkerError, contributions.ContributionError, RequirementRetrospectiveError) as exc:
        if not current():
            return {"status": "discarded"}
        post_result(workers.result_body(job, worker, "blocked: " + str(exc)[:200]))
        return {"status": "blocked", "reason": str(exc)}
    post_result(workers.result_body(job, worker, "Requirement retrospective recorded"))
    return outcome
