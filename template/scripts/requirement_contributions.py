"""Reviewed contribution integration, with trusted Git and injectable GitHub I/O.

Version two is deliberately separate from archived-child patch assembly. The
committed manifest and GitHub merge fact are the recovery journal; no local
status ledger authorizes a repeated merge.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import lifecycle_workers as workers
import requirement_integration as integration


class ContributionError(integration.RequirementIntegrationError):
    pass


def in_flight_children(root: Path, repo: str, requirement: str, target: str, *, adapter=None) -> dict:
    """Trusted coordinator ownership, including merged children awaiting manifest recovery."""
    if adapter is None:
        import publication_queue as adapter
    rows = adapter._gh(root, "pr", "list", "--state", "all", "--base", target,
                       "--limit", "100", "--json", "number")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise ContributionError("Requirement contribution inventory unavailable or exceeds bound")
    public = integration._public_requirement(root, requirement)
    owned = {}
    for row in rows:
        number = row["number"]
        comments = adapter._comments(root, repo, number)
        current = adapter._derive(root, adapter._pr(root, repo, number), comments)
        if adapter._malformed(current):
            raise ContributionError(f"malformed coordinator ownership for contribution PR #{number}")
        record = adapter._latest(root, number, comments)
        if record is None:
            continue
        identity = record.get("task_identity")
        if (isinstance(identity, dict) and identity.get("kind") == "contribution"
                and identity.get("requirement") == public and identity.get("target_branch") == target):
            change = identity["change"]
            if change in owned:
                raise ContributionError(f"ambiguous coordinator ownership for contribution {change}")
            owned[change] = {"change": change, "pr": number, "state": record["state"],
                             "reason": "contribution handed off; waiting for coordinator"}
    return owned


def seal(manifest: dict) -> dict:
    unsigned = {k: v for k, v in manifest.items() if k != "digest"}
    return {**unsigned, "digest": integration._digest(unsigned)}


def validate(manifest: dict, previous: dict | None = None) -> None:
    if manifest.get("version") != 2 or manifest.get("digest") != seal(manifest)["digest"]:
        raise ContributionError("reviewed contribution manifest version or digest is invalid")
    expected, children = manifest.get("expected_changes"), manifest.get("children")
    if (not isinstance(expected, list) or len(expected) < 2 or len(set(expected)) != len(expected)
            or not all(isinstance(c, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", c) for c in expected)
            or not isinstance(children, list)):
        raise ContributionError("mandatory contribution set is invalid")
    requirement = manifest.get("requirement")
    if not isinstance(requirement, str) or not (integration.ISSUE_RE.fullmatch(requirement) or re.fullmatch(r"pln_[0-9a-f]{32}", requirement)):
        raise ContributionError("invalid Requirement ownership")
    parent = manifest.get("work_identity")
    if not isinstance(parent, str) or not re.fullmatch(r"BR-[1-9][0-9]*", parent):
        raise ContributionError("invalid public Requirement work identity")
    if integration.ISSUE_RE.fullmatch(requirement) and parent != "BR-" + requirement.rsplit("#", 1)[1]:
        raise ContributionError("Requirement and public work identity disagree")
    if manifest.get("integration_branch") != f"requirement/{parent}":
        raise ContributionError("integration branch ownership mismatch")
    if not workers.HEAD.fullmatch(str(manifest.get("base", ""))):
        raise ContributionError("invalid integration base")
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict) or set(dependencies) != set(expected):
        raise ContributionError("dependency graph does not match mandatory changes")
    pending = set(expected)
    while pending:
        ready = {c for c in pending if isinstance(dependencies[c], list)
                 and all(d in expected and d != c and d not in pending for d in dependencies[c])}
        if not ready:
            raise ContributionError("unknown or cyclic contribution dependencies")
        pending -= ready
    seen = set()
    for child in children:
        if not isinstance(child, dict) or child.get("change") not in expected or child["change"] in seen:
            raise ContributionError("duplicate or unexpected contribution")
        if not set(dependencies[child["change"]]) <= seen:
            raise ContributionError("contribution integrated before its dependencies")
        seen.add(child["change"])
        for key in ("head", "contribution_base", "integrated_head"):
            if not workers.HEAD.fullmatch(str(child.get(key, ""))):
                raise ContributionError(f"invalid contribution {key}")
        identity = child.get("task_identity")
        if (not isinstance(identity, dict) or identity.get("kind") != "contribution"
                or identity.get("change") != child["change"]
                or identity.get("requirement") != requirement
                or identity.get("target_branch") != manifest["integration_branch"]
                or identity.get("source_issue") != child.get("source_issue")
                or identity.get("contribution_base") != child.get("contribution_base")
                or type(child.get("pr_number")) is not int
                or not (integration.ISSUE_RE.fullmatch(str(child.get("source_issue", "")))
                        or re.fullmatch(r"pln_[0-9a-f]{32}", str(child.get("source_issue", ""))))
                or not child.get("reviewed_evidence_digest")):
            raise ContributionError("contribution review identity is invalid")
    if previous is not None:
        validate(previous)
        for key in ("requirement", "repository", "work_identity", "base", "integration_branch", "expected_changes", "dependencies"):
            if previous.get(key) != manifest.get(key):
                raise ContributionError(f"immutable manifest boundary changed: {key}")
        if children[:len(previous["children"])] != previous["children"]:
            raise ContributionError("integrated contribution prefix changed, removed or reordered")


def read_manifest(checkout: Path, requirement: str, ref: str = "HEAD") -> dict:
    path = integration._candidate_manifest_path(requirement, checkout)
    try:
        value = json.loads(workers.harness_git(checkout, "show", f"{ref}:{path.as_posix()}"))
    except (workers.WorkerError, ValueError) as exc:
        raise ContributionError("integration branch has no exact owned manifest") from exc
    validate(value)
    if value["requirement"] != requirement:
        raise ContributionError("integration branch belongs to another Requirement")
    return value


def write_manifest(checkout: Path, manifest: dict) -> None:
    validate(manifest)
    path = checkout / integration._candidate_manifest_path(manifest["requirement"], checkout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    workers.harness_git(checkout, "add", "--", str(path.relative_to(checkout)))
    if workers.harness_git(checkout, "diff", "--cached", "--name-only").strip():
        workers.harness_git(checkout, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                            "commit", "-m", "Bind reviewed Requirement contributions")


def ensure_integration_branch(root: Path, *, requirement: str, repository: str, expected_changes: list[str],
                              dependencies: dict, source_repo: str | None = None, runner=subprocess.run) -> dict:
    """Create the owned branch once, or recover its exact committed manifest."""
    import managed_work_identity

    branch = f"requirement/BR-{requirement.rsplit('#', 1)[1]}"
    public_requirement = integration._public_requirement(root, requirement)
    source_repo = source_repo or f"https://github.com/{repository}.git"
    with tempfile.TemporaryDirectory(prefix="requirement-branch-") as temporary:
        checkout = workers.prepare_checkout(source_repo, temporary, "harness", "origin/main")
        base = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
        remote = workers.harness_git(checkout, "ls-remote", "origin", f"refs/heads/{branch}").strip()
        if remote:
            workers.harness_git(checkout, "fetch", "origin", branch)
            workers.harness_git(checkout, "checkout", "--detach", "FETCH_HEAD")
            manifest = read_manifest(checkout, public_requirement)
            if (manifest.get("repository") != repository or manifest["expected_changes"] != expected_changes
                    or manifest["dependencies"] != dependencies):
                raise ContributionError("existing integration branch has different ownership or mandatory graph")
        else:
            manifest = seal({"version": 2, "requirement": public_requirement, "repository": repository,
                             "work_identity": managed_work_identity.parent_identity(requirement), "base": base,
                             "integration_branch": branch, "expected_changes": expected_changes,
                             "dependencies": dependencies, "children": []})
            write_manifest(checkout, manifest)
            # Empty-ref lease refuses a same-name branch created concurrently.
            head = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
            push_fast_forward(checkout, branch, "", head, runner=runner)
        head = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
    return {"manifest": manifest, "branch": branch, "head": head}


def require_gates(candidate: dict) -> None:
    identity = candidate.get("task_identity")
    for name in ("review", "selected-checks", "semantic-verification"):
        gate = candidate.get("gates", {}).get(name, {})
        if gate.get("result") != "passed" or gate.get("identity") != identity or not gate.get("evidence"):
            raise ContributionError(f"contribution lacks current {name}")
    checks = candidate.get("gates", {}).get("required-checks", {})
    if (checks.get("result") != "passed" or checks.get("identity") != identity
            or checks.get("evidence", {}).get("head") != candidate.get("head")):
        raise ContributionError("contribution lacks exact-head required checks")


def recover_contribution_merge(checkout: Path, manifest: dict, pr: dict, candidate: dict) -> dict:
    """Append a proven GitHub merge once; an interrupted append never re-merges."""
    identity = candidate["task_identity"]
    prior = next((c for c in manifest["children"] if c["change"] == identity["change"]), None)
    if prior is not None:
        if prior["head"] != candidate["head"] or prior["pr_number"] != pr["number"]:
            raise ContributionError("integrated contribution head changed")
        return manifest
    require_gates(candidate)
    merge = pr.get("merge_commit_sha")
    if (not pr.get("merged") or pr.get("head", {}).get("sha") != candidate["head"]
            or pr.get("base", {}).get("ref") != manifest["integration_branch"]
            or not workers.HEAD.fullmatch(str(merge))):
        raise ContributionError("GitHub does not prove the exact contribution merge")
    workers.harness_git(checkout, "merge-base", "--is-ancestor", candidate["head"], merge)
    workers.harness_git(checkout, "merge-base", "--is-ancestor", merge, "HEAD")
    child = {"source_issue": identity["source_issue"], "change": identity["change"],
             "source_branch": pr["head"]["ref"], "pr_number": pr["number"],
             **({"work_identity": identity["work_identity"]} if identity.get("work_identity") else {}),
             "contribution_base": identity["contribution_base"], "head": candidate["head"],
             "task_identity": identity, "gates": candidate["gates"],
             "reviewed_evidence_digest": integration._digest(candidate["gates"]), "integrated_head": merge}
    updated = seal({**manifest, "children": [*manifest["children"], child]})
    validate(updated, manifest)
    return updated


def merge_reviewed_contribution(root: Path, repo: str, candidate: dict, *, adapter=None,
                                source_repo: str | None = None, runner=subprocess.run, expected_target_head: str | None = None,
                                claim_current=lambda: True) -> dict:
    """Coordinator-only ancestry preserving merge followed by a fast-forward manifest append."""
    if adapter is None:
        import publication_queue as adapter
    identity, number = candidate["task_identity"], candidate["number"]
    require_gates(candidate)
    if not claim_current():
        return {"state": "discarded"}
    target = identity["target_branch"]
    source_repo = source_repo or f"https://github.com/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="contribution-") as temporary:
        checkout = workers.prepare_checkout(source_repo, temporary, "harness", f"origin/{target}")
        manifest = read_manifest(checkout, identity["requirement"])
        if manifest.get("repository") != repo or manifest["integration_branch"] != target:
            raise ContributionError("contribution repository or target ownership changed")
        if identity.get("change") not in manifest["expected_changes"]:
            raise ContributionError("contribution is outside the mandatory child set")
        pr = adapter._pr(root, repo, number)
        if pr.get("head", {}).get("sha") != candidate["head"]:
            return {"state": "discarded"}
        if pr.get("base", {}).get("ref") != target:
            raise ContributionError("contribution PR target changed")
        existing = next((c for c in manifest["children"] if c["change"] == identity["change"]), None)
        if existing:
            recover_contribution_merge(checkout, manifest, pr, candidate)
        elif not pr.get("merged"):
            fresh = adapter.candidate_status(root, number, repo=repo)
            if fresh.get("task_identity") != identity or fresh.get("head") != candidate["head"]:
                return {"state": "discarded"}
            require_gates(fresh)
            workers.harness_git(checkout, "fetch", "origin", f"pull/{number}/head")
            if workers.harness_git(checkout, "rev-parse", "FETCH_HEAD").strip() != candidate["head"]:
                return {"state": "discarded"}
            target_head = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
            if expected_target_head is not None and target_head != expected_target_head:
                return {"state": "discarded"}
            workers.harness_git(checkout, "merge-base", "--is-ancestor", identity["contribution_base"], target_head)
            if not set(manifest["dependencies"][identity["change"]]) <= {c["change"] for c in manifest["children"]}:
                raise ContributionError("contribution dependencies are not integrated")
            conflicts = adapter.merge_conflicts(checkout, candidate["head"], target_head)
            if conflicts:
                adapter._integration_repair(root, repo, number, {},
                                            adapter.IntegrationRepairNeeded("contribution conflicts: " + ", ".join(conflicts)))
                return {"state": "integration-repair-pending", "number": number}
            if workers.harness_git(checkout, "ls-remote", "origin", f"refs/heads/{target}").split()[0] != target_head:
                return {"state": "discarded"}
            if not claim_current():
                return {"state": "discarded"}
            adapter._transition(root, repo, number, "contribution-integration-pending", candidate["head"],
                                task_identity=identity, inherit_identity=False, gates=fresh["gates"])
            response = adapter._gh(root, "api", "-X", "PUT", f"repos/{repo}/pulls/{number}/merge",
                                   data={"sha": candidate["head"], "merge_method": "merge"})
            if not isinstance(response, dict) or not response.get("merged"):
                raise ContributionError("protected contribution merge was not accepted")
            pr = adapter._pr(root, repo, number)
        workers.harness_git(checkout, "fetch", "origin", target)
        target_head = workers.harness_git(checkout, "rev-parse", "FETCH_HEAD").strip()
        workers.harness_git(checkout, "checkout", "--detach", target_head)
        manifest = read_manifest(checkout, identity["requirement"])
        updated = recover_contribution_merge(checkout, manifest, pr, candidate)
        write_manifest(checkout, updated)
        head = workers.harness_git(checkout, "rev-parse", "HEAD").strip()
        if head != target_head:
            if not claim_current():
                return {"state": "discarded"}
            push_fast_forward(checkout, target, target_head, head, runner=runner)
    # Contribution completion is nonterminal; the Requirement post-merge jobs process child retrospectives and cleanup.
    adapter._transition(root, repo, number, "contribution-integrated", candidate["head"],
                        task_identity=identity, inherit_identity=False, gates=candidate["gates"])
    return {"state": "contribution-integrated", "number": number, "integration_head": head}


def push_fast_forward(checkout: Path, branch: str, expected: str, head: str, *, runner=subprocess.run) -> None:
    observed = workers.harness_git(checkout, "ls-remote", "origin", f"refs/heads/{branch}").split()
    if (observed[0] if observed else "") != expected:
        raise ContributionError("integration branch moved before fast-forward publication")
    if expected:
        workers.harness_git(checkout, "merge-base", "--is-ancestor", expected, head)
    try:
        workers.push_validated(checkout, branch, expected, head, runner=runner)
    except workers.WorkerError as exc:
        raise ContributionError(str(exc)) from exc



def private_requirement(root: Path, manifest: dict) -> str:
    """Resolve a public opaque handle only with its exact authorized private mapping."""
    import private_lineage
    from _platform_common import read_platform_config

    value = manifest["requirement"]
    if integration.ISSUE_RE.fullmatch(value):
        return value
    repository = read_platform_config(root).get("development_backlog", {}).get("repository")
    if not repository:
        raise ContributionError("private Requirement resolution needs configured Backlog")
    source = f"{repository}#{manifest['work_identity'].removeprefix('BR-')}"
    private_lineage.require_handle(root, source, "requirement-integration", value)
    return source


def private_manifest(root: Path, manifest: dict, *, fetch_issue=None, prove_handle=None) -> dict:
    import private_lineage
    import managed_work_identity
    import requirement_intake

    parent = private_requirement(root, manifest)
    private_children = [child for child in manifest["children"] if not integration.ISSUE_RE.fullmatch(child["source_issue"])]
    assignments = {}
    if private_children:
        fetch = fetch_issue or requirement_intake.fetch_issue
        parent_body = str(fetch(root, *requirement_intake.issue_ref(parent)).get("body") or "")
        linked = requirement_intake.parse_requirement_body(parent_body)["children"]
        bodies = {ref: str(fetch(root, *requirement_intake.issue_ref(ref)).get("body") or "") for ref in linked}
        assignments = managed_work_identity.assignments(parent_body, parent, bodies)
    children = []
    for child in manifest["children"]:
        source = child["source_issue"]
        if not integration.ISSUE_RE.fullmatch(source):
            identity = child.get("work_identity", "")
            if not re.fullmatch(re.escape(manifest["work_identity"]) + r"/T[1-9][0-9]*", identity):
                raise ContributionError("private child lacks exact public work identity")
            matches = [ref for ref, ordinal in assignments.items()
                       if ref in linked and f"{manifest['work_identity']}/T{ordinal}" == identity]
            if len(matches) != 1:
                raise ContributionError("private child has no exact linked Backlog allocation")
            source = matches[0]
            (prove_handle or private_lineage.require_handle)(root, source, child["change"], child["source_issue"])
        children.append({**child, "source_issue": source})
    return {**manifest, "requirement": parent, "children": children}
