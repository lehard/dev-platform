"""Coordinator finalization after review/repair and archive-derived spec re-derivation.

Both operations are harness-owned: trusted code runs in a disposable checkout, reuses
content-bound evidence, validates every changed path and only then pushes with a lease
on the exact head the job was claimed for. GitHub I/O stays behind ``publication_queue``
so callers and tests can inject it.

* Finalization archives a reviewed candidate (``openspec_lifecycle.py archive --finalize``)
  and moves it to ``ready``. It never changes the task-content identity; a content change
  returns the candidate to review.
* Re-derivation resolves integration conflicts confined to archive-derived current-spec
  paths by taking main's spec and replaying the candidate's archived delta specs. It is
  bookkeeping only: checks still run on the result and any failure is integration repair.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from task_content_identity import equivalent_proofs
import lifecycle_workers as workers
import pr_review_gate as review_gate
import publication_queue as queue

REQUIRED_GATES = ("review", "selected-checks", "semantic-verification")
EVIDENCE_FILES = {"selected-checks": "automated-checks.json", "semantic-verification": "verification.md"}
SPEC_PATH = re.compile(r"openspec/specs/([^/]+)/spec\.md")
ARCHIVED_DELTA = re.compile(r"(openspec/changes/archive/(\d{4}-\d{2}-\d{2}-[^/]+))/specs/([^/]+)/spec\.md")
ARCHIVE_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-(.+)")


class RederivationFailed(RuntimeError):
    """A deterministic spec re-derivation could not be completed: integration repair."""


# ---- pure helpers -----------------------------------------------------------

def archived_deltas(paths) -> dict[str, set[str]]:
    """Archived change directories and the capabilities their delta specs name."""
    found: dict[str, set[str]] = {}
    for path in paths:
        match = ARCHIVED_DELTA.fullmatch(path)
        if match:
            found.setdefault(match.group(1), set()).add(match.group(3))
    return found


def derived_spec_paths(task_paths, overlap) -> set[str]:
    """Paths of ``overlap`` that are current-spec files materialized by the candidate's own archive."""
    capabilities = {cap for caps in archived_deltas(task_paths).values() for cap in caps}
    return {path for path in overlap if (m := SPEC_PATH.fullmatch(path)) and m.group(1) in capabilities}


def _archive_dir(checkout: Path, change: str) -> Path | None:
    matches = sorted((checkout / "openspec" / "changes" / "archive").glob(f"*-{change}"))
    matches = [m for m in matches if ARCHIVE_NAME.fullmatch(m.name) and ARCHIVE_NAME.fullmatch(m.name).group(1) == change]
    return matches[0] if len(matches) == 1 else None


def verify_reused_evidence(checkout: Path, gates: dict, identity: dict) -> list[str]:
    """Why the passed gates cannot be reused for this exact task content (empty means reusable)."""
    problems = []
    change = checkout / "openspec" / "changes" / identity["change"]
    if not change.is_dir():
        change = _archive_dir(checkout, identity["change"]) or change
    for name in REQUIRED_GATES:
        if not review_gate.reusable(checkout, gates.get(name), identity):
            problems.append(f"{name} evidence is missing or not bound to the current task content")
    for name, filename in EVIDENCE_FILES.items():
        recorded = (gates.get(name) or {}).get("evidence")
        path = change / filename
        if isinstance(recorded, dict) and recorded.get("harness_executed") is True:
            continue  # re-established by the harness for this identity, not by a developer file
        if not isinstance(recorded, dict) or not path.is_file():
            problems.append(f"{name} evidence file {filename} is missing")
        elif review_gate.file_reference(checkout, path)["sha256"] != recorded.get("sha256"):
            problems.append(f"{name} evidence file {filename} differs from the reviewed evidence")
    return problems


def validate_finalization_paths(repo: Path, base: str, result: str, change: str) -> list[str]:
    """Only the change's own archive move and its own spec materialization may change."""
    done = subprocess.run(["git", *workers.SAFE_GIT, "merge-base", "--is-ancestor", base, result], cwd=repo,
                          capture_output=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise workers.WorkerError("finalization is not a fast-forward from the claimed head")
    changed = [p for p in workers._git(repo, "diff", "--name-only", "--no-renames", "-z", base, result).split("\0") if p]
    active = f"openspec/changes/{change}/"
    archived = re.compile(rf"openspec/changes/archive/\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(change)}/")
    tree = workers._git(repo, "ls-tree", "-r", "--name-only", result, "openspec/changes/archive").splitlines()
    capabilities = {cap for caps in archived_deltas(
        p for p in tree if archived.match(p)).values() for cap in caps}
    for path in changed:
        match = SPEC_PATH.fullmatch(path)
        if not (path.startswith(active) or archived.match(path) or (match and match.group(1) in capabilities)):
            raise workers.WorkerError(f"finalization changed a path outside the archive: {path}")
    return changed


# ---- finalization -----------------------------------------------------------

def trusted_archiver(checkout: Path, change: str, env: dict[str, str]) -> None:
    """Run the platform's own archive entrypoint (this module's checkout, never the candidate's)."""
    script = Path(__file__).resolve().with_name("openspec_lifecycle.py")
    done = subprocess.run([sys.executable, str(script), "archive", change, "--finalize"], cwd=checkout, env=env,
                          stdin=subprocess.DEVNULL, text=True, capture_output=True, check=False)
    if done.returncode:
        raise workers.WorkerError("archive failed: " + (done.stderr.strip() or done.stdout.strip())[-400:])


def trusted_checks_runner(checkout: Path, env: dict[str, str]) -> None:
    """Run the platform's selected checks (trusted script) in the disposable checkout."""
    script = Path(__file__).resolve().with_name("select_checks.py")
    done = subprocess.run([sys.executable, str(script), "--base", "origin/main", "--execute"], cwd=checkout, env=env,
                          stdin=subprocess.DEVNULL, text=True, capture_output=True, check=False)
    if done.returncode:
        raise workers.WorkerError("selected checks failed: " + (done.stderr.strip() or done.stdout.strip())[-400:])


def reestablish_gates(checkout: Path, gates: dict, identity: dict, head: str,
                      checks_runner: Callable[..., None]) -> dict:
    """Bind selected-checks and semantic-verification to a repaired identity.

    A repair changes task content, so only still-proven gates carry over. The harness
    reruns the selected checks in the disposable checkout and re-binds the receipt that
    repairs may not edit; the review gate is never re-established here.
    """
    from openspec_lifecycle import verification_passed

    gates = dict(gates)
    if not review_gate.reusable(checkout, gates.get("review"), identity):
        raise workers.WorkerError("review evidence is missing or not bound to the current task content")
    change = checkout / "openspec" / "changes" / identity["change"]
    if not review_gate.reusable(checkout, gates.get("selected-checks"), identity):
        env = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
        checks_runner(checkout, env)
        gates["selected-checks"] = {"result": "passed", "identity": identity, "evidence": {
            "harness_executed": True, "head": workers._git(checkout, "rev-parse", "HEAD").strip(),
            "command": "select_checks --base origin/main --execute"}}
    if not review_gate.reusable(checkout, gates.get("semantic-verification"), identity):
        receipt = change / "verification.md"
        if not receipt.is_file() or not verification_passed(change):
            raise workers.WorkerError("semantic verification receipt is missing or not passing")
        gates["semantic-verification"] = {"result": "passed", "identity": identity,
                                          "evidence": review_gate.file_reference(checkout, receipt)}
    return gates


def execute_finalize(checkout: Path, job: dict, gates: dict, *, source_repo: str, branch: str, current_head,
                     runner=subprocess.run, archiver: Callable[..., None] | None = None, push_env=None,
                     before_push=None, claim_current=lambda: True,
                     checks_runner: Callable[..., None] | None = None) -> dict:
    """Archive the reviewed candidate in its disposable checkout; only the harness commits and pushes."""
    checkout = checkout.resolve()
    identity = job["task_identity"]
    change_name = identity["change"]
    actual = review_gate.task_identity(checkout, change_name)
    if not equivalent_proofs(checkout, identity.get("task_content"), actual["task_content"]):
        return {"status": "changed", "identity": actual}
    gates = reestablish_gates(checkout, gates, actual, job["head"], checks_runner or trusted_checks_runner)
    problems = verify_reused_evidence(checkout, gates, actual)
    if problems:
        raise workers.WorkerError("finalization cannot reuse evidence: " + "; ".join(problems))
    if (checkout / "openspec" / "changes" / change_name).is_dir():
        env = workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home")
        (archiver or trusted_archiver)(checkout, change_name, env)
    elif _archive_dir(checkout, change_name) is None:
        raise workers.WorkerError("change is neither active nor archived")
    workers._git(checkout, "add", "-A", "--", "openspec")
    leftovers = [p for p in workers._git(checkout, "diff", "--name-only", "-z").split("\0") if p] + [
        p for p in workers._git(checkout, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if p]
    if leftovers:
        raise workers.WorkerError("archive left changes outside openspec: " + ", ".join(leftovers[:5]))
    if workers._git(checkout, "diff", "--cached", "--name-only").strip():
        workers._git(checkout, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost",
                     "commit", "-m", f"Archive {change_name} after review")
    head = workers._git(checkout, "rev-parse", "HEAD").strip()
    fresh = review_gate.task_identity(checkout, change_name)
    if not equivalent_proofs(checkout, identity["task_content"], fresh["task_content"]):
        raise workers.WorkerError("finalization changed the task-content identity")
    if head == job["head"]:
        return {"status": "finalized", "pushed_head": None, "identity": fresh, "gates": gates}
    if current_head() != job["head"]:
        return {"status": "discarded"}
    harness = workers.prepare_harness(source_repo, checkout, checkout.parent, head)
    validate_finalization_paths(harness, job["head"], head, change_name)
    if before_push is not None:
        before_push(harness, head)
    if not claim_current():
        return {"status": "discarded"}
    workers.push_validated(harness, branch, job["head"], head, runner=runner, env=push_env)
    return {"status": "finalized", "pushed_head": head, "identity": fresh, "gates": gates}


def return_to_review(root: Path, repo: str, candidate: dict, head: str, fresh: dict, *, adapter=queue):
    """A task-content change after review repeats review and finalization; only still-proven gates carry."""
    kept = {name: gate for name, gate in candidate.get("gates", {}).items()
            if name != "review" and review_gate.reusable(root, gate, fresh)}
    return review_gate.offer(root, repo, candidate["number"], head, fresh, "review", gates=kept, adapter=adapter)


def run_claimed_finalize(root: Path, repo: str, candidate: dict, job: dict, *, source_repo: str, branch: str,
                         current_head, post_result, workdir: str, adapter=queue, runner=None, archiver=None,
                         worker: str = "worker", claim_current=None, push_env=None, checks_runner=None) -> dict:
    """Execute and advance one claimed exact-head finalize job, without the developer."""
    if job["kind"] != "finalize":
        raise workers.WorkerError(f"no finalization executor for {job['kind']}")
    number, identity = job["number"], job["task_identity"]
    if claim_current is None:
        def claim_current():
            comments = adapter._comments(root, repo, number)
            return workers.i_won(job, worker, comments, trusted_apps=adapter.trusted_apps(root),
                                 trusted_writers=adapter.trusted_writers(
                                     root, comments, (workers.CLAIM_PREFIX,), repo=repo))
    if not claim_current():
        return {"status": "discarded"}
    observed = adapter._derive(root, adapter._pr(root, repo, number), adapter._comments(root, repo, number))
    if workers.build_job(observed) != job or not isinstance(identity, dict):
        return {"status": "discarded"}
    gates = observed.get("gates", {})
    runner = runner or subprocess.run

    def before_push(harness, head):
        if not claim_current():
            return
        workers._git(harness, "checkout", "--detach", head)
        fresh = review_gate.task_identity(harness, identity["change"])
        post_result(workers.result_body(job, worker, "validated-push", head, task_identity=fresh))

    def blocked(reason: str) -> dict:
        if claim_current():
            adapter._transition(root, repo, number, "blocked-escalation", job["head"], task_identity=identity,
                                inherit_identity=False, red_gate={"name": "finalize", "identity": identity,
                                                                  "evidence": reason[:500]})
            post_result(workers.result_body(job, worker, "failed: " + reason[:200]))
        return {"status": "blocked-escalation", "reason": reason}

    try:
        checkout = workers.prepare_checkout(source_repo, str(Path(workdir).resolve()), "finalize-checkout", job["head"])
        outcome = execute_finalize(checkout, job, gates, source_repo=source_repo, branch=branch,
                                   current_head=current_head, runner=runner, archiver=archiver, push_env=push_env,
                                   before_push=before_push, claim_current=claim_current, checks_runner=checks_runner)
    except workers.WorkerError as exc:
        return blocked(str(exc))
    if outcome["status"] == "discarded":
        return outcome
    if outcome["status"] == "changed":
        if current_head() != job["head"] or not claim_current():
            return {"status": "discarded"}
        return_to_review(root, repo, observed, job["head"], outcome["identity"], adapter=adapter)
        post_result(workers.result_body(job, worker, "returned-to-review"))
        return {"status": "returned-to-review"}
    head = outcome.get("pushed_head") or job["head"]
    if current_head() != head or not claim_current():
        return {**outcome, "status": "discarded"}
    if head != job["head"]:
        adapter._comment(root, repo, number, {"kind": "update", "previous": job["head"], "head": head,
                                              "worker_job": workers.job_id(job)})
    fresh = outcome["identity"]
    adapter._transition(root, repo, number, "ready", head, task_identity=fresh, inherit_identity=False,
                        gates={name: {**gate, "identity": fresh} for name, gate in outcome.get("gates", gates).items()
                               if review_gate.reusable(checkout, gate, fresh)})
    post_result(workers.result_body(job, worker, "finalized", outcome.get("pushed_head")))
    return {"status": "finalized", "pushed_head": outcome.get("pushed_head")}


# ---- archive-derived spec re-derivation ---------------------------------------

def _openspec(checkout: Path, *args: str) -> None:
    executable = shutil.which("openspec")
    if not executable:
        raise RederivationFailed("OpenSpec CLI is required to re-derive archived specs")
    done = subprocess.run([executable, *args], cwd=checkout, stdin=subprocess.DEVNULL, text=True,
                          capture_output=True, check=False,
                          env=workers.credential_free_env(dict(os.environ), checkout.parent / "llm-home"))
    if done.returncode:
        raise RederivationFailed(f"openspec {args[0]} failed: " + (done.stdout + done.stderr).strip()[-400:])


def _replay_archived_delta(checkout: Path, archive_dir: str) -> None:
    """Re-apply one archived change's delta specs on the checkout's (main's) current specs."""
    original = checkout / archive_dir
    change = ARCHIVE_NAME.fullmatch(original.name).group(1)
    active = checkout / "openspec" / "changes" / change
    if active.exists():
        raise RederivationFailed(f"{change} is already active; cannot replay its archived delta")
    shutil.copytree(original, active)
    shutil.rmtree(original)
    try:
        _openspec(checkout, "archive", change, "--yes")
    finally:
        # Restore the candidate's archive byte for byte whatever date the replay used.
        for created in (checkout / "openspec" / "changes" / "archive").glob(f"*-{change}"):
            shutil.rmtree(created, ignore_errors=True)
        shutil.rmtree(active, ignore_errors=True)
        workers._git(checkout, "checkout", "HEAD", "--", archive_dir)


def rederive_archived_specs(*, source_repo: str, branch: str, head: str, task_paths, workdir: str,
                            replay: Callable[[Path, str], None] | None = None,
                            validate: Callable[[Path], None] | None = None, runner=subprocess.run,
                            push_env=None, claim_current=lambda: True) -> tuple[str, str]:
    """Merge main into the candidate, deriving the candidate's spec paths by replaying its archived deltas.

    Returns ``(new_head, main_sha)`` after a lease-protected push, or raises ``RederivationFailed``.
    The replay is bookkeeping: it never replaces required checks on the resulting candidate.
    """
    deltas = archived_deltas(task_paths)
    if not deltas:
        raise RederivationFailed("candidate has no archived delta specs to re-derive from")
    names = {ARCHIVE_NAME.fullmatch(Path(d).name).group(1) for d in deltas}
    if len(names) != 1:
        raise RederivationFailed("candidate archives more than one change; cannot re-derive")
    change = names.pop()
    capabilities = {cap for caps in deltas.values() for cap in caps}
    spec_paths = {f"openspec/specs/{cap}/spec.md" for cap in capabilities}
    checkout = workers.prepare_checkout(source_repo, str(Path(workdir).resolve()), "rederive-checkout", head)
    workers._git(checkout, "fetch", "--no-tags", "origin", "main")
    main_sha = workers._git(checkout, "rev-parse", "FETCH_HEAD").strip()
    if subprocess.run(["git", *workers.SAFE_GIT, "merge-base", "--is-ancestor", main_sha, head], cwd=checkout,
                      capture_output=True, check=False, stdin=subprocess.DEVNULL).returncode == 0:
        return head, main_sha  # idempotent: the head already contains this main
    before = review_gate.task_identity(checkout, change)
    merge = subprocess.run(["git", *workers.SAFE_GIT, "merge", "--no-commit", "--no-ff", main_sha], cwd=checkout,
                           text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
    merging = (checkout / ".git" / "MERGE_HEAD").is_file()
    if merge.returncode and not merging:
        raise RederivationFailed("merge of main failed: " + (merge.stderr or merge.stdout).strip()[-300:])
    outside = set(workers._git(checkout, "diff", "--name-only", "--diff-filter=U").split()) - spec_paths
    if outside:
        raise RederivationFailed("conflicts outside archive-derived spec paths: " + ", ".join(sorted(outside)[:8]))
    for path in sorted(spec_paths):
        if subprocess.run(["git", *workers.SAFE_GIT, "cat-file", "-e", f"{main_sha}:{path}"], cwd=checkout,
                          capture_output=True, check=False, stdin=subprocess.DEVNULL).returncode == 0:
            workers._git(checkout, "checkout", main_sha, "--", path)
        else:
            workers._git(checkout, "rm", "-q", "-f", "--ignore-unmatch", "--", path)
    for archive_dir in sorted(deltas):
        (replay or _replay_archived_delta)(checkout, archive_dir)
    (validate or (lambda path: _openspec(path, "validate", "--all", "--strict", "--no-interactive")))(checkout)
    workers._git(checkout, "add", "-A")
    if workers._git(checkout, "diff", "--name-only", "--diff-filter=U").strip():
        raise RederivationFailed("unresolved conflicts remain after re-derivation")
    workers._git(checkout, "-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost", "commit", "-q",
                 "-m", f"Re-derive archived specs of {change} on main")
    result = workers._git(checkout, "rev-parse", "HEAD").strip()
    parents = workers._git(checkout, "rev-list", "--parents", "-n", "1", result).split()[1:]
    if parents != [head, main_sha]:
        raise RederivationFailed("re-derivation did not produce a merge of the claimed head and main")
    both = (set(workers._git(checkout, "diff", "--name-only", head, result).split())
            & set(workers._git(checkout, "diff", "--name-only", main_sha, result).split()))
    if both - spec_paths:
        raise RederivationFailed("re-derivation changed paths beyond archive-derived specs: "
                                 + ", ".join(sorted(both - spec_paths)[:8]))
    after = review_gate.task_identity(checkout, change)
    if not equivalent_proofs(checkout, before["task_content"], after["task_content"]):
        raise RederivationFailed("re-derivation changed the task-content identity")
    if not claim_current():
        raise RederivationFailed("claim lost before push")
    workers.push_validated(checkout, branch, head, result, runner=runner, env=push_env)
    return result, main_sha


def derived_merge_only(root: Path, head: str, proven: str, prior_main: str, task_paths) -> bool:
    """Whether ``head`` is a merge of ``proven`` and main differing from both only on archive-derived specs."""
    from _platform_common import run_git

    spec_paths = {f"openspec/specs/{cap}/spec.md" for caps in archived_deltas(task_paths).values() for cap in caps}
    if not spec_paths:
        return False
    names = []
    for other in (proven, prior_main):
        done = run_git(["diff", "--name-only", other, head], cwd=root, check=False)
        if done.returncode:
            return False
        names.append(set(done.stdout.splitlines()))
    return not (names[0] & names[1]) - spec_paths


def prepare_derived_specs(root: Path, repo: str, number: int, pr: dict, head: str, task_paths, **options) -> tuple[str, str]:
    """Coordinator entry: re-derive, record the coordinator update and return ``(head, main)``."""
    import tempfile

    source = options.pop("source_repo", None) or f"https://github.com/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="rederive-") as workdir:
        try:
            new_head, main_sha = rederive_archived_specs(source_repo=source, branch=pr["head"]["ref"], head=head,
                                                        task_paths=task_paths, workdir=workdir, **options)
        except workers.WorkerError as exc:
            raise RederivationFailed(str(exc)) from exc
    queue._comment(root, repo, number, {"kind": "update", "previous": head, "head": new_head, "base": main_sha})
    return new_head, main_sha
