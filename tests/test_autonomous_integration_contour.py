"""Autonomous integration contour: integration repair, non-blocking queue, friction attribution, post-merge jobs."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("candidate_lifecycle", SCRIPTS / "candidate_lifecycle.py")
queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")
gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
contour = load_platform_module("integration_contour", SCRIPTS / "integration_contour.py")
friction = load_platform_module("agent_friction", SCRIPTS / "agent_friction.py")
retrospective = load_platform_module("requirement_retrospective", SCRIPTS / "requirement_retrospective.py")
composition_module = load_platform_module("requirement_composition", SCRIPTS / "requirement_composition.py")
contributions_module = load_platform_module("requirement_contributions", SCRIPTS / "requirement_contributions.py")

from test_pr_review_gate import IDENTITY, PROVIDER, ROUTE, QueueFixture, git  # noqa: E402
from test_post_review_finalization import Remote, RemoteFixture  # noqa: E402

FAILED_LINK = "https://github.com/o/r/actions/runs/1/job/2"

# Unattributed friction is read only inside agent_friction.AMBIGUOUS_WINDOW_DAYS
# of now, so window fixtures are relative to the run time, not fixed dates.
_NOW = datetime.now(timezone.utc).replace(microsecond=0)
WINDOW_OLDER = (_NOW - timedelta(days=3)).isoformat()
WINDOW_STARTED = (_NOW - timedelta(days=2)).isoformat()
WINDOW_INSIDE = (_NOW - timedelta(days=1)).isoformat()

HEAD, BASE, MAIN = "a" * 40, "b" * 40, "c" * 40
REQUIREMENT = "acme/backlog#7"
CHILDREN = ["acme/backlog#8", "acme/backlog#9"]


class Multi:
    """GitHub I/O for several PRs; real transitions, trust and job records."""

    def __init__(self, heads: dict[int, str]):
        self.heads, self.comments, self.merged = dict(heads), {n: [] for n in heads}, set()
        self.stack = ExitStack()

    def pr(self, _root, _repo, number):
        return {"number": number, "state": "closed" if number in self.merged else "open", "merged": number in self.merged,
                "head": {"sha": self.heads[number], "ref": f"agent/br-7-t{number}-task"}, "labels": []}

    def post(self, _root, *args, data=None, **kwargs):
        number = int(re.search(r"issues/(\d+)/comments", " ".join(args)).group(1))
        self.comments[number].append({"id": len(self.comments[number]) + 1, "author_association": "OWNER",
                                      "body": data["body"]})

    def __enter__(self):
        for name, value in (("_pr", self.pr), ("_comments", lambda r, repo, n: list(self.comments[n]))):
            self.stack.enter_context(mock.patch.object(queue, name, side_effect=value))
        self.stack.enter_context(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
        for name in ("_project_lifecycle_label", "_label"):
            self.stack.enter_context(mock.patch.object(queue, name))
        self.stack.enter_context(mock.patch.object(queue, "_gh", side_effect=self.post))
        self.stack.enter_context(mock.patch.object(queue, "_repo", return_value="o/r"))
        return self

    def __exit__(self, *args):
        self.stack.close()

    def candidate(self, number):
        return queue._derive(ROOT, self.pr(ROOT, "o/r", number), self.comments[number])

    def ready(self, number, *, identity=None):
        queue._transition(ROOT, "o/r", number, "ready", self.heads[number],
                          task_identity=identity or {"branch": f"agent/br-7-t{number}-task", "head": self.heads[number]},
                          inherit_identity=False, route=ROUTE)

    def run_worker(self, *, prepare=None, checks="passed"):
        def merge(command, **kwargs):
            if command[:4] == ["gh", "api", "-X", "PUT"]:
                self.merged.add(int(command[4].split("/")[-2]))
            return subprocess.CompletedProcess(command, 0, "", "")

        order = [(n, n, {"branch": f"agent/br-7-t{n}-task"}) for n in sorted(self.heads)]
        with mock.patch.object(queue, "_queued", return_value=order), \
                mock.patch.object(queue, "_require_finalized"), \
                mock.patch.object(queue, "_prepare", side_effect=prepare or (lambda r, repo, n, a, pr: (self.heads[n], BASE))), \
                mock.patch.object(queue, "_main", return_value=BASE), \
                mock.patch.object(queue, "required_check_state_for_ref",
                                  return_value=SimpleNamespace(kind=checks, detail="validate", checks=(
                                      {"name": "validate", "workflow": "Platform CI", "link": FAILED_LINK,
                                       "state": "FAILURE" if checks == "failed" else "SUCCESS"},
                                      {"name": "lint", "workflow": "Platform CI", "state": "SUCCESS",
                                       "link": "https://github.com/o/r/actions/runs/1/job/3"}))), \
                mock.patch.object(queue.subprocess, "run", side_effect=merge):
            return queue.worker(ROOT)


def setUpModule() -> None:
    # Local-log scenarios: durable coordinator evidence (GitHub) is covered by the
    # coordinator-operations tests, so these scenarios never reach GitHub.
    for module in {friction, sys.modules["agent_friction"]}:
        patcher = mock.patch.object(module, "read_durable_events", return_value=[])
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


def head_for(number: int) -> str:
    return f"{number:x}" * 40


class IntegrationScenarioTests(unittest.TestCase):
    def test_overlapping_but_clean_candidate_proceeds_to_checks_on_the_merged_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Remote(Path(tmp))
            root = repo.root
            git(root, "checkout", "-qb", "agent/clean")
            (root / "src.py").write_text("value = 0\nline = 1\n")
            git(root, "commit", "-qam", "candidate")
            candidate = git(root, "rev-parse", "HEAD")
            git(root, "checkout", "-q", "main")
            (root / "src.py").write_text("main = 1\nvalue = 0\n")  # same path, different region
            git(root, "commit", "-qam", "main moves")
            git(root, "push", "-q", "origin", "HEAD:main")
            git(root, "fetch", "-q", "origin")
            main = git(root, "rev-parse", "origin/main")
            self.assertEqual(queue.merge_conflicts(root, candidate, main), [])

    def test_real_conflict_is_detected_without_touching_the_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Remote(Path(tmp))
            root = repo.root
            git(root, "checkout", "-qb", "agent/clash")
            (root / "src.py").write_text("value = 1\n")
            git(root, "commit", "-qam", "candidate")
            candidate = git(root, "rev-parse", "HEAD")
            git(root, "checkout", "-q", "main")
            (root / "src.py").write_text("value = 2\n")
            git(root, "commit", "-qam", "main moves")
            git(root, "push", "-q", "origin", "HEAD:main")
            git(root, "fetch", "-q", "origin")
            self.assertEqual(queue.merge_conflicts(root, candidate, git(root, "rev-parse", "origin/main")), ["src.py"])

    def test_head_blocked_by_an_error_does_not_stop_the_next_ready_candidate(self):
        with Multi({7: head_for(7), 8: head_for(8)}) as multi:
            multi.ready(7), multi.ready(8)

            def prepare(root, repo, number, admission, pr):
                if number == 7:
                    raise queue.QueueError("branch protection refused the update")
                return multi.heads[number], BASE

            result = multi.run_worker(prepare=prepare)
            self.assertEqual((result["state"], result["number"]), ("merged", 8))
            self.assertEqual(multi.candidate(7)["state"], "blocked-escalation")
            self.assertTrue(any("#7" in item for item in result["skipped"]))

    def test_candidate_owned_by_other_work_is_skipped_for_the_next(self):
        with Multi({7: head_for(7), 8: head_for(8)}) as multi:
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", multi.heads[7], task_identity={"head": "x"},
                              inherit_identity=False, red_gate={"name": "review", "evidence": "rounds"})
            multi.ready(8)
            result = multi.run_worker()
            self.assertEqual((result["state"], result["number"]), ("merged", 8))

    def test_a_blocked_only_queue_still_reports_blocked(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            result = multi.run_worker(prepare=mock.Mock(side_effect=queue.QueueError("boom")))
            self.assertEqual(result["state"], "blocked")

    def test_merge_marks_the_candidate_for_post_merge_jobs(self):
        with Multi({8: head_for(8)}) as multi:
            multi.ready(8)
            self.assertEqual(multi.run_worker()["state"], "merged")
            merged = multi.candidate(8)
            self.assertEqual(merged["state"], "merged")
            self.assertEqual(workers.build_job(merged)["kind"], "retrospective")


MANIFEST_GENERATOR = """\
import json, pathlib, sys
tree = pathlib.Path(sys.argv[1])
names = sorted(path.stem for path in (tree / "entries").glob("*.txt"))
target = tree / "template/dev-platform/platform-manifest.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"entries": names}, indent=2) + "\\n")
"""


class ComposeGeneratedManifestConflictTests(unittest.TestCase):
    """A Requirement composition conflicting with main only in the declared platform manifest merges unattended."""

    MANIFEST = "template/dev-platform/platform-manifest.json"
    BRANCH = "requirement/BR-7"
    NUMBER = 11

    def setUp(self):
        from test_requirement_contribution_composition import Repository

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        manifest_path = self.MANIFEST

        class ManifestRepository(Repository):
            # Main declares the platform manifest generated from the start; each child archives a delta
            # spec and the first child also adds a manifest entry, as finalized children leave them.
            def commit(self, message):
                root = self.root
                if message == "base":
                    (root / "dev-platform/checks.toml").write_text(
                        f'[settings]\nfull_commands = ["python3 gen.py --check"]\n'
                        f'[[generated_files]]\npath = "{manifest_path}"\n'
                        'regenerate = ["python3", "gen.py", "{tree}"]\ncheck = ["python3", "gen.py", "--check"]\n')
                    (root / "gen.py").write_text(MANIFEST_GENERATOR)
                    (root / "entries").mkdir()
                    (root / "entries/base.txt").write_text("base\n")
                    subprocess.run(["python3", "gen.py", str(root)], cwd=root, check=True)
                if message in {"first", "second"}:
                    delta = root / "openspec/changes" / message / "specs" / f"cap-{message}/spec.md"
                    delta.parent.mkdir(parents=True)
                    delta.write_text(f"## ADDED Requirements\n\n### Requirement: {message}\n")
                if message == "first":
                    (root / "entries/first.txt").write_text("first\n")
                    subprocess.run(["python3", "gen.py", str(root)], cwd=root, check=True)
                return super().commit(message)

        source = tmp / "source"
        source.mkdir()
        fixture = ManifestRepository(source)
        first, second = fixture.child("first", 8), fixture.child("second", 9)
        fixture.integrate(first), fixture.integrate(second)
        for name in fixture.manifest["expected_changes"]:
            archived = source / "openspec/changes/archive" / f"2026-10-27-{name}"
            archived.parent.mkdir(parents=True, exist_ok=True)
            (source / "openspec/changes" / name).rename(archived)
            spec = source / "openspec/specs" / f"cap-{name}/spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text(f"### Requirement: {name}\n")
        self.head = fixture.commit("archive children")
        self.composition = composition_module.composition_identity(source, fixture.manifest)
        self.base = fixture.base
        # Main moves on after admission: a neighbouring manifest entry, nothing else in common.
        git(source, "switch", "-q", "main")
        (source / "entries/main.txt").write_text("main\n")
        subprocess.run(["python3", "gen.py", str(source)], cwd=source, check=True)
        self.main = fixture.commit("main adds an entry")
        self.remote = tmp / "remote.git"
        git(tmp, "clone", "-q", "--bare", str(source), str(self.remote))
        # The queue's trusted default-branch checkout: declaration and generator come from main.
        self.trusted = tmp / "trusted"
        git(tmp, "clone", "-q", str(self.remote), str(self.trusted))
        self.comments, self.merged, self.gh_calls = [], False, []
        self.task_paths = set(git(source, "diff", "--name-only", f"{self.base}...{self.head}").splitlines())

    def remote_head(self):
        return git(self.remote, "rev-parse", f"refs/heads/{self.BRANCH}")

    def pr(self, _root, _repo, number):
        return {"number": number, "state": "closed" if self.merged else "open", "merged": self.merged,
                "head": {"sha": self.remote_head(), "ref": self.BRANCH}, "base": {"ref": "main"}, "labels": []}

    def gh(self, _root, *args, data=None, **kwargs):
        self.gh_calls.append(args)
        path = next(arg for arg in args if arg.startswith("repos/"))
        if path.endswith("/comments"):
            self.comments.append({"id": len(self.comments) + 1, "author_association": "OWNER", "body": data["body"]})
        elif "/compare/" in path:
            return {"files": [{"filename": name} for name in sorted(self.task_paths)]}
        elif not path.endswith("/labels"):
            raise AssertionError(f"unexpected GitHub call: {args}")
        return {}

    def run_commands(self, original):
        def run(command, **kwargs):
            if command[:2] != ["gh", "api"]:
                return original(command, **kwargs)
            self.gh_calls.append(tuple(command))
            if command[2:4] == ["-X", "PUT"] and command[4] == f"repos/o/r/pulls/{self.NUMBER}/merge":
                self.assertIn(f"sha={self.remote_head()}", command)
                self.merged = True
            return subprocess.CompletedProcess(command, 0, "", "")
        return run

    def test_composition_conflicting_only_in_the_platform_manifest_merges_without_an_operator(self):
        trusted = self.trusted
        self.assertEqual(queue.merge_conflicts(trusted, self.head, self.main), [self.MANIFEST])
        final = sys.modules["post_review_finalization"]
        real_prepare = final.prepare_derived_specs

        replayed = []

        def replay(checkout, archive_dir):
            # Deterministic stand-in for `openspec archive`: main never touched these capabilities.
            name = archive_dir.rsplit("/", 1)[-1].split("-", 3)[-1]
            replayed.append(name)
            git(checkout, "checkout", "HEAD", "--", f"openspec/specs/cap-{name}/spec.md")

        def prepare_locally(*args, **kwargs):
            return real_prepare(*args, source_repo=self.remote.as_uri(), replay=replay, validate=lambda checkout: None,
                                **kwargs)

        admission = {"head": self.head, "base": self.base, "branch": self.BRANCH, "comment_id": 0}
        with ExitStack() as stack:
            enter = stack.enter_context
            enter(mock.patch.object(queue, "_pr", side_effect=self.pr))
            enter(mock.patch.object(queue, "_comments", side_effect=lambda *a: list(self.comments)))
            enter(mock.patch.object(queue, "_gh", side_effect=self.gh))
            enter(mock.patch.object(queue, "_repo", return_value="o/r"))
            enter(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
            enter(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
            enter(mock.patch.object(queue, "_project_lifecycle_label"))
            enter(mock.patch.object(queue, "_queued", return_value=[(1, self.NUMBER, admission)]))
            # Each boundary below has its own coverage; this scenario proves the integration path between them.
            enter(mock.patch.object(queue, "_require_finalized"))
            composition_gates = enter(mock.patch.object(queue, "require_composition_finalized"))
            refreshed = enter(mock.patch.object(queue, "refresh_composition_checks"))
            enter(mock.patch.object(queue, "required_check_state_for_ref",
                                    return_value=SimpleNamespace(kind="passed", detail="validate")))
            derived = enter(mock.patch.object(final, "prepare_derived_specs", side_effect=prepare_locally))
            enter(mock.patch.object(queue.subprocess, "run", side_effect=self.run_commands(subprocess.run)))
            queue._transition(trusted, "o/r", self.NUMBER, "ready", self.head, task_identity=self.composition,
                              inherit_identity=False)
            result = queue.worker(trusted)
            candidate = queue._derive(trusted, self.pr(trusted, "o/r", self.NUMBER), self.comments)

        merged = self.remote_head()
        self.assertEqual(result, {"state": "merged", "number": self.NUMBER, "head": merged})
        self.assertEqual(candidate["state"], "merged")
        derived.assert_called_once()
        self.assertEqual(replayed, ["first", "second"])  # the composition derivation, in manifest child order
        refreshed.assert_called_once_with(trusted, "o/r", self.NUMBER, merged)
        composition_gates.assert_any_call(trusted, "o/r", self.NUMBER, merged)
        # One coordinator merge of the admitted head and main, fast-forwarded onto the branch.
        self.assertEqual(git(self.remote, "rev-list", "--parents", "-n", "1", merged).split()[1:], [self.head, self.main])
        self.assertEqual(json.loads(git(self.remote, "show", f"{merged}:{self.MANIFEST}")),
                         {"entries": ["base", "first", "main"]})
        self.assertEqual(git(self.remote, "diff", "--name-only", self.head, merged).splitlines(),
                         ["entries/main.txt", self.MANIFEST])
        # The composition's reviewed content is unchanged by the derived merge.
        with tempfile.TemporaryDirectory() as checkout:
            git(Path(checkout), "clone", "-q", str(self.remote), "after")
            after = Path(checkout) / "after"
            git(after, "checkout", "-q", merged)
            manifest = contributions_module.read_manifest(after, self.composition["requirement"])
            self.assertTrue(final.equivalent_proofs(after, self.composition["task_content"],
                                                    composition_module.composition_identity(after, manifest)["task_content"]))
        # No writer, no repair or integration-merge job, no operator escalation, no GitHub branch update.
        self.assertEqual(candidate["next_job"]["kind"], "retrospective")
        self.assertEqual(candidate.get("attempts", {}).get("integration-repair", 0), 0)
        self.assertFalse(any(str(row["body"]).startswith(queue.ATTENTION_PREFIX) for row in self.comments))
        self.assertFalse(any("update-branch" in " ".join(call) for call in self.gh_calls))
        updates = [json.loads(row["body"][len(queue.PREFIX):]) for row in self.comments
                   if row["body"].startswith(queue.PREFIX)]
        self.assertEqual([(u["kind"], u["previous"], u["head"], u["base"]) for u in updates if u["kind"] == "update"],
                         [("update", self.head, merged, self.main)])


class IntegrationRepairBoundTests(unittest.TestCase):
    def conflict(self, number=7):
        return mock.Mock(side_effect=queue.IntegrationRepairNeeded("merge of current main conflicts in: src.py"))

    def test_conflict_offers_one_bounded_job_and_reruns_are_idempotent(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            result = multi.run_worker(prepare=self.conflict())
            self.assertEqual(result["state"], "waiting")
            candidate = multi.candidate(7)
            self.assertEqual(candidate["state"], "integration-repair-pending")
            self.assertEqual(candidate["red_gate"]["name"], "integration")
            job = workers.build_job(candidate)
            self.assertEqual((job["kind"], job["attempt"]), ("integration-repair", 1))
            records = len(multi.comments[7])
            prepare = self.conflict()
            multi.run_worker(prepare=prepare)
            prepare.assert_not_called()  # owned by the repair job: skipped, not re-prepared
            self.assertEqual(len(multi.comments[7]), records)

    def test_quick_task_conflict_without_a_route_gets_the_recorded_default_claude_route(self):
        with Multi({7: head_for(7)}) as multi:
            queue._transition(ROOT, "o/r", 7, "ready", multi.heads[7],
                              task_identity={"branch": "agent/br-7-t7-task", "head": multi.heads[7]}, inherit_identity=False)
            result = multi.run_worker(prepare=self.conflict())
            self.assertEqual(result["state"], "waiting")
            candidate = multi.candidate(7)
            self.assertEqual(candidate["route"], {"provider": "claude", "profile": "standard", "change": "br-7-t7-task"})
            job = workers.build_job(candidate)
            self.assertEqual((job["kind"], job["providers"]), ("integration-repair", ["claude"]))

    def test_managed_conflict_without_a_recorded_route_blocks_explicitly_and_publishes_no_job(self):
        with Multi({7: head_for(7)}) as multi:
            queue._transition(ROOT, "o/r", 7, "ready", multi.heads[7],
                              task_identity={"change": "managed-change", "task_content": {"digest": "d"}}, inherit_identity=False)
            result = multi.run_worker(prepare=self.conflict())
            self.assertEqual(result["state"], "blocked")
            self.assertIn("no originating task route and is not a Requirement composition or quick task", result["reason"])
            self.assertIsNone(workers.build_job(multi.candidate(7)))

    def test_interrupted_offer_is_completed_on_the_next_run(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "integration-repair-pending", multi.heads[7],
                              task_identity={"head": "x"}, set_attempts={"integration-repair": 1},
                              red_gate={"name": "integration", "identity": multi.heads[7], "evidence": "conflict"})
            self.assertIsNone(multi.candidate(7)["next_job"])
            multi.run_worker()
            self.assertEqual(workers.build_job(multi.candidate(7))["kind"], "integration-repair")

    def test_clean_trial_merge_after_a_failed_derived_merge_offers_an_llm_free_integration_merge(self):
        merge_only = mock.Mock(side_effect=queue.IntegrationRepairNeeded("derived merge failed: x", merge_only=True))
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            multi.run_worker(prepare=merge_only)
            candidate = multi.candidate(7)
            self.assertEqual((candidate["state"], candidate["red_gate"]["merge_only"]), ("integration-repair-pending", True))
            job = workers.build_job(candidate)
            self.assertEqual((job["kind"], job["attempt"]), ("integration-merge", 1))
            self.assertNotIn("providers", job)
            self.assertFalse(any(str(row.get("body", "")).startswith(queue.ATTENTION_PREFIX) for row in multi.comments[7]))

    def test_interrupted_merge_only_offer_republishes_the_integration_merge(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "integration-repair-pending", multi.heads[7],
                              task_identity={"head": "x"}, set_attempts={"integration-repair": 1},
                              red_gate={"name": "integration", "identity": multi.heads[7], "evidence": "x", "merge_only": True})
            multi.run_worker()
            self.assertEqual(workers.build_job(multi.candidate(7))["kind"], "integration-merge")

    def test_failing_integration_check_creates_a_repair_job_not_a_block(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            multi.run_worker(checks="failed")
            candidate = multi.candidate(7)
            self.assertEqual(candidate["state"], "integration-repair-pending")
            self.assertEqual(candidate["red_gate"]["name"], "required-checks")
            # The writer brief reads the log of exactly the failed check through its recorded identity.
            self.assertEqual(candidate["red_gate"]["evidence"]["failed_checks"],
                             [{"name": "validate", "workflow": "Platform CI", "state": "FAILURE", "link": FAILED_LINK}])
            self.assertIn("validate", candidate["red_gate"]["evidence"]["detail"])

    def test_bound_blocks_the_candidate_after_two_attempts_and_the_next_one_still_merges(self):
        def conflict_on_7(root, repo, number, admission, pr):
            if number == 7:
                raise queue.IntegrationRepairNeeded("conflict")
            return multi.heads[number], BASE

        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            for attempt in (1, 2):
                multi.run_worker(prepare=conflict_on_7)
                self.assertEqual(multi.candidate(7)["attempts"]["integration-repair"], attempt)
                multi.ready(7)  # the repair finished without a content change: ready again
            multi.heads[8], multi.comments[8] = head_for(8), []
            multi.ready(8)
            result = multi.run_worker(prepare=conflict_on_7)
            self.assertEqual((result["state"], result["number"]), ("merged", 8))
            blocked = multi.candidate(7)
            self.assertEqual(blocked["state"], "blocked-escalation")
            self.assertIn("exhausted", blocked["red_gate"]["evidence"])


class RepairFixture(unittest.TestCase):
    """A real source repository whose candidate conflicts with main."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Remote(Path(self.tmp.name))
        root = self.repo.root
        git(root, "checkout", "-qb", "agent/example")
        change = root / "openspec/changes/example"
        change.mkdir(parents=True)
        (change / "proposal.md").write_text("## Why\nx\n\n## What Changes\n- y\n")
        (change / "tasks.md").write_text("- [x] implement\n")
        (change / ".managed-task.json").write_text('{"change":"example", "source_issue":"owner/backlog#1"}')
        (root / "src.py").write_text("value = 1\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "candidate")
        self.repo.push("agent/example")
        self.identity = gate.task_identity(root, "example")
        git(root, "checkout", "-q", "main")
        (root / "src.py").write_text("value = 2\n")
        git(root, "commit", "-qam", "main moves")
        git(root, "push", "-q", "origin", "HEAD:main")
        git(root, "fetch", "-q", "origin")
        git(root, "checkout", "-q", "agent/example")
        self.results = []

    def runner(self, resolve):
        def run(command, **kwargs):
            if command[0] == "git":
                return subprocess.run(command, **kwargs)
            resolve(Path(kwargs["cwd"]))
            return subprocess.CompletedProcess(command, 0, "", "")
        return run

    def offer(self, fixture, *, attempt=1):
        queue._transition(self.repo.root, "o/r", 7, "integration-repair-pending", fixture.head, task_identity=self.identity,
                          inherit_identity=False, set_attempts={"integration-repair": attempt},
                          red_gate={"name": "integration", "identity": fixture.head, "evidence": "conflict in src.py"})
        queue.publish_job(self.repo.root, "o/r", 7, "integration-repair", fixture.head,
                          task_identity=self.identity, attempt=attempt)

    def post(self, fixture):
        def post_result(body):
            fixture.comments.append({"id": len(fixture.comments) + 1, "author_association": "OWNER", "body": body})
            self.results.append(body)
        return post_result

    def repair(self, fixture, resolve, **options):
        candidate = fixture.candidate()
        job = workers.build_job(candidate)
        self.assertEqual(job["kind"], "integration-repair")
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            return contour.run_claimed_integration_repair(
                self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(), branch="agent/example",
                allowed_paths=options.pop("allowed_paths", []), llm_command=["writer"], current_head=self.repo.head,
                post_result=self.post(fixture), workdir=workdir, runner=self.runner(resolve),
                claim_current=options.pop("claim_current", lambda: True), worker="w", provider=PROVIDER, **options)


def resolve_value(checkout: Path) -> None:
    (checkout / "src.py").write_text("value = 12\n")


class IntegrationRepairTests(RepairFixture):
    def test_conflict_changing_task_content_returns_through_review_and_finalization(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, resolve_value)
            self.assertEqual(outcome["status"], "integrated")
            after = self.repo.head("agent/example")
            main = git(self.repo.remote, "rev-parse", "refs/heads/main")
            self.assertEqual(git(self.repo.remote, "rev-list", "--parents", "-n", "1", after).split()[1:], [before, main])
            self.assertEqual(git(self.repo.remote, "show", f"{after}:src.py"), "value = 12")
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "review-pending")
            self.assertEqual(workers.build_job(candidate)["kind"], "review")
            self.assertNotEqual(candidate["task_identity"]["task_content"]["digest"],
                                self.identity["task_content"]["digest"])
            self.assertNotIn("review", candidate["gates"])
            # The coordinator can prove the pushed head (update marker), so preparation will accept it.
            self.assertIn(after, [e.get("head") for e in queue._events(self.repo.root, "o/r", 7) if e.get("kind") == "update"])

    def test_out_of_scope_or_workflow_edits_are_refused_and_a_new_bounded_attempt_is_offered(self):
        def tamper(checkout: Path) -> None:
            (checkout / ".github/workflows").mkdir(parents=True)
            (checkout / ".github/workflows/ci.yml").write_text("on: push\n")
            (checkout / "src.py").write_text("value = 12\n")

        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, tamper)
            self.assertEqual(outcome["status"], "failed")
            self.assertEqual(self.repo.head("agent/example"), before)
            job = workers.build_job(fixture.candidate())
            self.assertEqual((job["kind"], job["attempt"]), ("integration-repair", 2))

    def test_unresolved_conflicts_do_not_push_and_the_bound_blocks_after_two_attempts(self):
        with RemoteFixture(self.repo) as fixture, mock.patch.object(queue, "_label"):
            self.offer(fixture, attempt=2)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, lambda checkout: None)
            self.assertEqual(outcome["status"], "blocked-escalation")
            self.assertEqual(self.repo.head("agent/example"), before)
            self.assertEqual(fixture.candidate()["state"], "blocked-escalation")

    def offer_red_check(self, fixture, failed_checks):
        queue._transition(self.repo.root, "o/r", 7, "integration-repair-pending", fixture.head, task_identity=self.identity,
                          inherit_identity=False, set_attempts={"integration-repair": 1},
                          red_gate={"name": "required-checks", "identity": fixture.head,
                                    "evidence": {"detail": "required check failed on the integrated candidate: validate",
                                                 **({"failed_checks": failed_checks} if failed_checks is not None else {})}})
        queue.publish_job(self.repo.root, "o/r", 7, "integration-repair", fixture.head,
                          task_identity=self.identity, attempt=1)

    def test_red_check_writer_brief_carries_the_failed_log_excerpt(self):
        prompts, reads = [], []

        def read_log(repo, run, job):
            reads.append((repo, run, job))
            return "\n".join(f"line {n}" for n in range(200)) + "\nSyntaxError: too many statically nested blocks\n"

        def resolve(checkout: Path) -> None:
            (checkout / "src.py").write_text("value = 12\n")

        def runner(command, **kwargs):
            if command[0] == "git":
                return subprocess.run(command, **kwargs)
            prompts.append(command[-1])
            resolve(Path(kwargs["cwd"]))
            return subprocess.CompletedProcess(command, 0, "", "")

        with RemoteFixture(self.repo) as fixture:
            self.offer_red_check(fixture, [{"name": "validate", "workflow": "Platform CI", "state": "FAILURE",
                                            "link": FAILED_LINK}])
            candidate = fixture.candidate()
            job = workers.build_job(candidate)
            with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
                outcome = contour.run_claimed_integration_repair(
                    self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(), branch="agent/example",
                    allowed_paths=[], llm_command=["writer"], current_head=self.repo.head, post_result=self.post(fixture),
                    workdir=workdir, runner=runner, claim_current=lambda: True, worker="w", provider=PROVIDER,
                    read_log=read_log)
        self.assertEqual(outcome["status"], "integrated")
        self.assertEqual(reads, [("o/r", "1", "2")])
        brief = json.loads(prompts[0][prompts[0].index("Brief: ") + len("Brief: "):])
        [check] = brief["failed_checks"]
        self.assertEqual((check["name"], check["link"]), ("validate", FAILED_LINK))
        self.assertTrue(check["log_excerpt"].endswith("SyntaxError: too many statically nested blocks"))
        self.assertEqual(len(check["log_excerpt"].splitlines()), contour.FAILED_LOG_LINES)
        self.assertEqual(brief["evidence"], "required check failed on the integrated candidate: validate")

    def test_red_check_brief_without_evidence_is_refused_before_any_writer_starts(self):
        def no_writer(command, **kwargs):
            if command[0] != "git":
                raise AssertionError(f"a writer started without failed-check evidence: {command}")
            return subprocess.run(command, **kwargs)

        cases = ((None, lambda *a: "log", "records no failed check identity"),
                 ([{"name": "validate", "state": "FAILURE"}], lambda *a: "log", "has no GitHub Actions job link"),
                 ([{"name": "validate", "link": FAILED_LINK}], lambda *a: "  \n", "failed log of check validate is empty"))
        for failed_checks, read_log, refusal in cases:
            with self.subTest(refusal=refusal), RemoteFixture(self.repo) as fixture:
                self.offer_red_check(fixture, failed_checks)
                candidate = fixture.candidate()
                job = workers.build_job(candidate)
                before = (self.repo.head("agent/example"), len(self.results))
                with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir, \
                        self.assertRaisesRegex(workers.WorkerError, "integration-repair brief refused: .*" + refusal):
                    contour.run_claimed_integration_repair(
                        self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(),
                        branch="agent/example", allowed_paths=[], llm_command=["writer"], current_head=self.repo.head,
                        post_result=self.post(fixture), workdir=workdir, runner=no_writer, claim_current=lambda: True,
                        worker="w", provider=PROVIDER, read_log=read_log)
                # Nothing pushed, no result posted and no repair attempt spent: the job stays offered as it was.
                self.assertEqual((self.repo.head("agent/example"), len(self.results)), before)
                self.assertEqual(workers.build_job(fixture.candidate()), job)

    def test_unreadable_failed_log_names_the_job_and_gh_output(self):
        failed = subprocess.CompletedProcess([], 1, "", "HTTP 404: Not Found")
        with mock.patch.object(contour.subprocess, "run", return_value=failed) as run, \
                self.assertRaisesRegex(workers.WorkerError, "Actions job 2 is unreadable: HTTP 404"):
            contour.read_failed_log("o/r", "1", "2")
        self.assertEqual(run.call_args.args[0], ["gh", "run", "view", "1", "--job", "2", "--log-failed", "-R", "o/r"])

    def offer_merge(self, fixture, *, attempt=1):
        queue._transition(self.repo.root, "o/r", 7, "integration-repair-pending", fixture.head, task_identity=self.identity,
                          inherit_identity=False, set_attempts={"integration-repair": attempt},
                          red_gate={"name": "integration", "identity": fixture.head, "evidence": "derived merge failed",
                                    "merge_only": True})
        queue.publish_job(self.repo.root, "o/r", 7, "integration-merge", fixture.head,
                          task_identity=self.identity, attempt=attempt)

    def merge(self, fixture):
        candidate = fixture.candidate()
        job = workers.build_job(candidate)
        self.assertEqual(job["kind"], "integration-merge")

        def no_writer(command, **kwargs):
            if command[0] != "git":
                raise AssertionError(f"integration merge started a non-git process: {command}")
            return subprocess.run(command, **kwargs)
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            return contour.run_claimed_integration_repair(
                self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(), branch="agent/example",
                allowed_paths=[], llm_command=None, current_head=self.repo.head, post_result=self.post(fixture),
                workdir=workdir, runner=no_writer, claim_current=lambda: True, worker="w", provider=None)

    def test_integration_merge_meeting_a_conflict_starts_no_writer_and_offers_integration_repair(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer_merge(fixture)
            before = self.repo.head("agent/example")
            outcome = self.merge(fixture)
            self.assertEqual(outcome["status"], "failed")
            self.assertIn("needs a writer integration repair: conflicts in: src.py", outcome["reason"])
            self.assertEqual(self.repo.head("agent/example"), before)
            candidate = fixture.candidate()
            self.assertNotIn("merge_only", candidate["red_gate"])
            job = workers.build_job(candidate)
            self.assertEqual((job["kind"], job["attempt"], job["providers"]), ("integration-repair", 2, [PROVIDER]))

    def test_clean_integration_merge_pushes_the_merge_of_main_without_a_writer(self):
        root = self.repo.root
        (root / "src.py").write_text("value = 2\n")  # the same content as main: the merge is clean
        git(root, "commit", "-qam", "candidate takes main's value")
        self.repo.push("agent/example")
        self.identity = gate.task_identity(root, "example")
        with RemoteFixture(self.repo) as fixture:
            self.offer_merge(fixture)
            before = self.repo.head("agent/example")
            outcome = self.merge(fixture)
            self.assertEqual(outcome["status"], "integrated")
            after = self.repo.head("agent/example")
            main = git(self.repo.remote, "rev-parse", "refs/heads/main")
            self.assertEqual(git(self.repo.remote, "rev-list", "--parents", "-n", "1", after).split()[1:], [before, main])
            self.assertTrue(any('"kind":"integration-merge"' in body or "integration-merge" in body for body in self.results))

    def test_integration_merge_refuses_a_writer_command(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer_merge(fixture)
            candidate = fixture.candidate()
            job = workers.build_job(candidate)
            with self.assertRaisesRegex(workers.WorkerError, "integration-merge job runs no writer"):
                contour.run_claimed_integration_repair(
                    self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(), branch="agent/example",
                    allowed_paths=[], llm_command=["writer"], current_head=self.repo.head, post_result=self.post(fixture),
                    workdir=self.tmp.name, claim_current=lambda: True, worker="w", provider=None)

    def test_filters_and_textconv_planted_in_the_writer_checkout_never_execute(self):
        sentinel = Path(self.tmp.name) / "sentinel"

        def plant(checkout: Path) -> None:
            resolve_value(checkout)
            (checkout / ".gitattributes").write_text("* filter=evil diff=evil\n")
            for key in ("filter.evil.clean", "diff.evil.textconv"):
                subprocess.run(["git", "config", key, f"touch {sentinel} #"], cwd=checkout, check=True)

        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            outcome = self.repair(fixture, plant, allowed_paths=[".gitattributes"])
            self.assertEqual(outcome["status"], "integrated")
            self.assertFalse(sentinel.exists())

    def test_nested_git_metadata_in_the_writer_tree_is_refused_and_its_filter_never_runs(self):
        sentinel = Path(self.tmp.name) / "sentinel"

        def plant(checkout: Path) -> None:
            resolve_value(checkout)
            evil = checkout / "evilgit"
            subprocess.run(["git", "init", "-q", "--bare", str(evil)], check=True)
            for key, value in (("core.bare", "false"), ("filter.pwn.clean", f"touch {sentinel} #")):
                subprocess.run(["git", "--git-dir", str(evil), "config", key, value], check=True)
            (checkout / "sub").mkdir()
            (checkout / "sub/.git").write_text("gitdir: ../evilgit\n")
            (checkout / "sub/.gitattributes").write_text("* filter=pwn\n")
            (checkout / "sub/x").write_text("x")

        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, plant, allowed_paths=["sub/", "evilgit/"])
            self.assertEqual(outcome, {"status": "failed", "reason": "nested git metadata: sub/.git"})
            self.assertEqual(self.repo.head("agent/example"), before)
            self.assertFalse(sentinel.exists())

    def test_lost_claim_prevents_the_push(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            calls = iter([True])
            outcome = self.repair(fixture, resolve_value, claim_current=lambda: next(calls, False))
            self.assertEqual(outcome["status"], "discarded")
            self.assertEqual(self.repo.head("agent/example"), before)

    def test_push_without_advancement_recovers_as_review_and_a_stale_second_run_is_discarded(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            candidate = fixture.candidate()
            with mock.patch.object(queue, "_comment", side_effect=RuntimeError("crash after push")):
                with self.assertRaisesRegex(RuntimeError, "crash after push"):
                    self.repair(fixture, resolve_value)
            self.assertNotEqual(self.repo.head("agent/example"), candidate["head"])
            recovered = fixture.candidate()
            self.assertEqual(recovered["state"], "review-pending")
            self.assertIn("recover validated", recovered["reason"])
            # The old job is no longer offered for the moved head.
            self.assertEqual(workers.build_job(recovered)["kind"], "review")
            self.assertEqual(self.repo.head("agent/example"), recovered["head"])

    def test_validated_unchanged_push_is_recovered_idempotently(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            old = fixture.candidate()
            job = workers.build_job(old)
            # A harness-pushed repair that left task content unchanged, interrupted before advancement.
            git(self.repo.root, "commit", "-q", "--allow-empty", "-m", "repair")
            self.repo.push("agent/example")
            fixture.comments.append({"id": 100, "author_association": "OWNER", "body": workers.result_body(
                job, "w", "validated-push", self.repo.head("agent/example"), task_identity=self.identity)})
            recovered = fixture.candidate()
            self.assertEqual((recovered["state"], recovered["red_gate"]), ("ready", None))
            pr = queue._pr(self.repo.root, "o/r", 7)
            self.assertTrue(contour.recover_integration_repair(self.repo.root, "o/r", 7, pr, list(fixture.comments)))
            self.assertEqual(fixture.candidate()["state"], "ready")
            count = len(fixture.comments)
            self.assertFalse(contour.recover_integration_repair(self.repo.root, "o/r", 7, pr, list(fixture.comments)))
            self.assertEqual(len(fixture.comments), count)

    def test_validated_integration_merge_push_is_recovered_by_its_own_job(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer_merge(fixture)
            job = workers.build_job(fixture.candidate())
            git(self.repo.root, "commit", "-q", "--allow-empty", "-m", "merge")
            self.repo.push("agent/example")
            fixture.comments.append({"id": 100, "author_association": "OWNER", "body": workers.result_body(
                job, "w", "validated-push", self.repo.head("agent/example"), task_identity=self.identity)})
            self.assertEqual(fixture.candidate()["state"], "ready")

    def test_validated_push_recovery_without_a_recorded_lineage_head_is_an_error(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            job = workers.build_job(fixture.candidate())
            git(self.repo.root, "commit", "-q", "--allow-empty", "-m", "repair")
            self.repo.push("agent/example")
            fixture.comments.append({"id": 100, "author_association": "OWNER", "body": workers.result_body(
                job, "w", "validated-push", self.repo.head("agent/example"), task_identity=self.identity)})
            pr = queue._pr(self.repo.root, "o/r", 7)
            count = len(fixture.comments)
            with mock.patch.object(queue, "_latest", return_value=None):
                with self.assertRaisesRegex(queue.QueueError, "no recorded lineage head"):
                    contour.recover_integration_repair(self.repo.root, "o/r", 7, pr, list(fixture.comments))
            self.assertEqual(len(fixture.comments), count)

    def test_unchanged_identity_reuses_evidence_and_reruns_required_checks(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            good = {"result": "passed", "identity": IDENTITY, "evidence": {}}
            queue._transition(ROOT, "o/r", 7, "integration-repair-pending", HEAD, task_identity=IDENTITY,
                              inherit_identity=False,
                              gates={"review": good, "required-checks": {**good, "evidence": "old"}})
            new_head = "d" * 40
            fixture.head = new_head
            state = contour.advance_after_repair(ROOT, "o/r", {**fixture.candidate(), "head": HEAD, "task_identity": IDENTITY,
                                                              "gates": {"review": good, "required-checks": good}},
                                                 new_head, IDENTITY, None)
            self.assertEqual(state, "ready")
            candidate = fixture.candidate()
            self.assertEqual(sorted(candidate["gates"]), ["review"])
            self.assertIsNone(candidate["red_gate"])

    def test_validation_refuses_results_that_skip_main_or_escape_scope(self):
        root = self.repo.root
        git(root, "fetch", "-q", "origin")
        main = git(root, "rev-parse", "origin/main")
        head = self.repo.head("agent/example")
        git(root, "checkout", "-q", "--detach", head)
        (root / "src.py").write_text("value = 12\n")
        git(root, "commit", "-qam", "fix without main")
        with self.assertRaisesRegex(workers.WorkerError, "integrate current main"):
            contour.validate_integration_result(root, head, git(root, "rev-parse", "HEAD"), main, ["src.py"])
        git(root, "checkout", "-q", "--detach", head)
        subprocess.run(["git", "merge", "--no-commit", "--no-ff", main], cwd=root, capture_output=True, stdin=subprocess.DEVNULL)
        (root / "src.py").write_text("value = 12\n")
        (root / "other.py").write_text("x = 1\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "merge")
        result = git(root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(workers.WorkerError, "outside candidate scope: other.py"):
            contour.validate_integration_result(root, head, result, main, ["src.py"])
        self.assertEqual(contour.validate_integration_result(root, head, result, main, ["src.py", "other.py"]),
                         ["other.py", "src.py"])


def merged_pr(head=HEAD, number=7, merged_at="2026-10-30T10:00:00Z"):
    return {"number": number, "state": "closed", "merged": True, "merged_at": merged_at, "head": {"sha": head}}


def record(state, *, attempts=None, head=HEAD, identity=None, number=7):
    body = lifecycle.marker_body(lifecycle.build_handoff_record(
        number=number, state=state, head=head, task_identity=identity or {"branch": "agent/br-7-t8-task", "head": head},
        gates={}, red_gate=None, not_reverified=[], attempts=attempts or {}, next_job=None,
        at="2026-10-06T00:00:00+00:00"))
    return {"id": 1, "author_association": "OWNER", "body": body}


def receipt(job_kind, attempt, outcome, row_id, head=HEAD, number=7):
    job = {"number": number, "kind": job_kind, "head": head, "attempt": attempt}
    return {"id": row_id, "author_association": "OWNER", "body": workers.result_body(job, "w", outcome)}


class PostMergeDerivationTests(unittest.TestCase):
    def derive(self, *rows, flagged=True):
        base = record("merged", attempts={"post-merge": 1} if flagged else {})
        return lifecycle.derive_candidate(merged_pr(), [base, *rows])

    def test_chain_is_retrospective_then_terminal_then_cleanup_then_done(self):
        self.assertEqual(self.derive()["next_job"]["kind"], "retrospective")
        rows = [receipt("retrospective", 0, "task-recorded", 2)]
        self.assertEqual(self.derive(*rows)["next_job"]["kind"], "terminal-reconciliation")
        rows.append(receipt("terminal-reconciliation", 0, "requirement-reconciled", 3))
        self.assertEqual(self.derive(*rows)["next_job"]["kind"], "cleanup")
        rows.append(receipt("cleanup", 0, "cleaned", 4))
        self.assertIsNone(self.derive(*rows)["next_job"])

    def test_candidate_not_merged_by_this_contour_offers_nothing(self):
        self.assertIsNone(self.derive(flagged=False)["next_job"])

    def test_failed_attempt_retries_a_new_attempt_and_exhaustion_stops_with_a_reason(self):
        rows = [receipt("retrospective", 0, "failed: network", 2)]
        job = self.derive(*rows)["next_job"]
        self.assertEqual((job["kind"], job["attempt"]), ("retrospective", 1))
        rows += [receipt("retrospective", 1, "blocked: ambiguous", 3), receipt("retrospective", 2, "failed: x", 4)]
        exhausted = self.derive(*rows)
        self.assertIsNone(exhausted["next_job"])
        self.assertIn("exhausted", exhausted["reason"])

    def test_derivation_is_pure_so_an_interrupted_run_is_offered_again(self):
        self.assertEqual(self.derive()["next_job"], self.derive()["next_job"])
        # A validated-push or discarded receipt completes nothing.
        rows = [receipt("retrospective", 0, "discarded: head moved", 2)]
        self.assertEqual(self.derive(*rows)["next_job"]["attempt"], 0)

    def test_an_excluded_pr_is_neither_read_nor_offered(self):
        comments = [record("merged", attempts={"post-merge": 1})]
        read = []
        result = workers.work_next(
            frozenset({"retrospective"}), list_prs=lambda: [merged_pr()],
            comments_for=lambda n: read.append(n) or comments, post_comment=lambda n, body: self.fail("no claim"),
            worker="w", exclude_prs=frozenset({7}), trusted_apps=frozenset(), trusted_writers=frozenset())
        self.assertEqual((result["status"], read), ("idle", []))

    def test_work_next_claims_a_post_merge_job_of_a_merged_candidate(self):
        comments = [record("merged", attempts={"post-merge": 1})]
        posted = []
        result = workers.work_next(
            frozenset({"retrospective"}), list_prs=lambda: [merged_pr()], comments_for=lambda n: comments + posted,
            post_comment=lambda n, body: posted.append({"id": 50, "author_association": "OWNER", "body": body}),
            worker="w", trusted_apps=frozenset(), trusted_writers=frozenset())
        self.assertEqual((result["status"], result["job"]["kind"]), ("claimed", "retrospective"))

    def settle_run(self, *rows, dry_run=False, labels=()):
        comments = [record("merged", attempts={"post-merge": 1}), *rows]
        settled = []
        workers.work_next(
            frozenset({"retrospective", "terminal-reconciliation", "cleanup"}),
            list_prs=lambda: [{**merged_pr(), "labels": [{"name": name} for name in labels]}],
            comments_for=lambda n: comments, post_comment=lambda n, body: None, worker="w", dry_run=True,
            settle=None if dry_run else settled.append, trusted_apps=frozenset(), trusted_writers=frozenset())
        return settled

    def test_only_a_settled_chain_is_marked_settled(self):
        done = [receipt("retrospective", 0, "task-recorded", 2), receipt("terminal-reconciliation", 0, "ok", 3),
                receipt("cleanup", 0, "cleaned", 4)]
        self.assertEqual(self.settle_run(*done), [7])
        self.assertEqual(self.settle_run(*done, labels=(workers.SETTLED_LABEL,)), [])
        self.assertEqual(self.settle_run(*done, dry_run=True), [])
        self.assertEqual(self.settle_run(*done[:2]), [])  # cleanup still open
        exhausted = [receipt("retrospective", attempt, "failed: x", 2 + attempt) for attempt in range(3)]
        self.assertEqual(self.settle_run(*exhausted), [])

    def test_a_failed_settle_label_fails_the_run(self):
        done = [receipt("retrospective", 0, "task-recorded", 2), receipt("terminal-reconciliation", 0, "ok", 3),
                receipt("cleanup", 0, "cleaned", 4)]

        def refuse(number):
            raise workers.WorkerError("label write refused")
        with self.assertRaisesRegex(workers.WorkerError, "label write refused"):
            workers.work_next(
                frozenset({"cleanup"}), list_prs=lambda: [merged_pr()],
                comments_for=lambda n: [record("merged", attempts={"post-merge": 1}), *done],
                post_comment=lambda n, body: None, worker="w", settle=refuse,
                trusted_apps=frozenset(), trusted_writers=frozenset())


class CandidateDiscoveryTests(unittest.TestCase):
    """BR-882: a merged PR with an open post-merge obligation never ages out of discovery."""

    def reader(self, *, window=(), labeled=(), fail=None):
        calls = []

        def read(*args):
            calls.append(args)
            path = args[-1]
            if fail and fail in path:
                raise workers.WorkerError(f"gh failed: {path}")
            if "state=open" in path:
                return [{"number": 1, "state": "open"}]
            if "pulls?state=closed" in path:
                return [{"number": n, "state": "closed", "merged_at": "2026-10-30T10:00:00Z", "labels": []} for n in window]
            if "issues?state=closed" in path:
                return list(labeled)
            number = int(path.rsplit("/", 1)[1])
            return {"number": number, "state": "closed" if number != 1 else "open", "merged": number != 1,
                    "merged_at": None if number == 1 else "2026-10-29T10:00:00Z", "head": {"sha": HEAD}}
        return read, calls

    def test_labeled_merged_pr_outside_the_window_is_a_candidate(self):
        labeled = [{"number": 678, "pull_request": {}, "labels": [{"name": workers.MERGED_LABEL}]},
                   {"number": 600, "pull_request": {}, "labels": [{"name": workers.SETTLED_LABEL}]},
                   {"number": 900, "pull_request": {}, "labels": []},
                   {"number": 5, "labels": []}]  # an Issue, not a PR
        read, calls = self.reader(window=(900,), labeled=labeled)
        found = workers.candidate_prs("o/r", include_merged=True, gh_json=read)
        self.assertEqual([pr["number"] for pr in found], [1, 900, 678])
        self.assertIn(("api", "--paginate", "repos/o/r/issues?state=closed&labels=lifecycle%3Amerged&per_page=100"), calls)
        self.assertEqual([c for c in calls if c[-1].startswith("repos/o/r/pulls/")], [("api", "repos/o/r/pulls/678")])

    def test_open_obligation_outside_the_window_is_offered(self):
        read, _ = self.reader(labeled=[{"number": 7, "pull_request": {}, "labels": [{"name": workers.MERGED_LABEL}]}])
        posted = []
        result = workers.work_next(
            frozenset({"retrospective"}), list_prs=lambda: workers.candidate_prs("o/r", include_merged=True, gh_json=read),
            comments_for=lambda n: [record("merged", attempts={"post-merge": 1})] + posted if n == 7 else [],
            post_comment=lambda n, body: posted.append({"id": 50, "author_association": "OWNER", "body": body}),
            worker="w", trusted_apps=frozenset(), trusted_writers=frozenset())
        self.assertEqual((result["status"], result["job"]["number"]), ("claimed", 7))

    def test_unreadable_label_listing_fails_instead_of_a_partial_set(self):
        read, _ = self.reader(fail="issues?state=closed")
        with self.assertRaisesRegex(workers.WorkerError, "issues"):
            workers.candidate_prs("o/r", include_merged=True, gh_json=read)

    def test_selected_prs_are_read_directly(self):
        read, calls = self.reader()
        found = workers.candidate_prs("o/r", include_merged=True, only_prs=frozenset({681, 1}), gh_json=read)
        self.assertEqual([pr["number"] for pr in found], [1, 681])
        self.assertEqual([c[-1] for c in calls], ["repos/o/r/pulls/1", "repos/o/r/pulls/681"])
        self.assertEqual([pr["number"] for pr in workers.candidate_prs(
            "o/r", include_merged=False, only_prs=frozenset({681, 1}), gh_json=read)], [1])

    def test_settled_pr_in_the_recent_page_is_not_a_candidate(self):
        read, calls = self.reader(window=(900, 901))
        settled = lambda *args: [{**pr, "labels": [{"name": workers.SETTLED_LABEL}] if pr["number"] == 901 else []}
                                 for pr in read(*args)] if "pulls?state=closed" in args[-1] else read(*args)
        found = workers.candidate_prs("o/r", include_merged=True, gh_json=settled)
        self.assertEqual([pr["number"] for pr in found], [1, 900])

    def test_lazy_listing_returns_unread_stubs_for_the_label_tail(self):
        labeled = [{"number": 678, "pull_request": {"merged_at": "2026-10-01T10:00:00Z"},
                    "labels": [{"name": workers.MERGED_LABEL}]}]
        read, calls = self.reader(labeled=labeled)
        found = workers.candidate_prs("o/r", include_merged=True, gh_json=read, lazy=True)
        self.assertEqual(found[-1], {"number": 678, "state": "closed", "merged": True, "unread": True,
                                     "labels": [{"name": workers.MERGED_LABEL}], "merged_at": "2026-10-01T10:00:00Z"})
        self.assertFalse([c for c in calls if c[-1].startswith("repos/o/r/pulls/")])
        self.assertEqual(workers.resolve_candidate("o/r", found[-1], gh_json=read)["head"]["sha"], HEAD)


class FreshFirstSelectionTests(unittest.TestCase):
    """BR-939: a fresh merged PR is served before the historical tail, reading only what it needs."""

    KINDS = frozenset({"retrospective", "terminal-reconciliation", "cleanup"})

    def run_next(self, prs, *, resolve=None, settle=None, kinds=KINDS):
        read = []
        result = workers.work_next(
            kinds, list_prs=lambda: prs,
            comments_for=lambda n: read.append(n) or [record("merged", attempts={"post-merge": 1}, number=n)],
            post_comment=lambda n, body: self.fail("dry run claims nothing"), worker="w", dry_run=True,
            settle=settle, resolve_pr=resolve, trusted_apps=frozenset(), trusted_writers=frozenset())
        return result, read

    def test_newest_merge_is_offered_first_without_reading_older_prs(self):
        old = [merged_pr(number=n, merged_at=f"2026-10-0{n % 9 + 1}T10:00:00Z") for n in range(324, 330)]
        fresh = merged_pr(number=808, merged_at="2026-10-30T12:00:00Z")
        result, read = self.run_next([*old, fresh])
        self.assertEqual((result["status"], result["job"]["number"], read), ("dry-run", 808, [808]))

    def test_merge_time_not_number_decides(self):
        late = merged_pr(number=700, merged_at="2026-10-31T09:00:00Z")
        result, read = self.run_next([merged_pr(number=810, merged_at="2026-10-30T09:00:00Z"), late])
        self.assertEqual((result["job"]["number"], read), (700, [700]))

    def test_open_pr_comes_before_merged(self):
        opened = {"number": 950, "state": "open", "head": {"sha": HEAD}}
        _, read = self.run_next([merged_pr(number=808, merged_at="2026-10-30T12:00:00Z"), opened])
        self.assertEqual(read[0], 950)

    def test_unread_stub_is_resolved_only_when_reached(self):
        resolved = []
        stub = {"number": 400, "state": "closed", "merged": True, "unread": True, "labels": [],
                "merged_at": "2026-10-01T10:00:00Z"}
        fresh = merged_pr(number=808, merged_at="2026-10-30T12:00:00Z")
        result, _ = self.run_next([stub, fresh], resolve=lambda pr: resolved.append(pr["number"]) or merged_pr(number=400))
        self.assertEqual((result["job"]["number"], resolved), (808, []))
        _, read = self.run_next([stub], resolve=lambda pr: resolved.append(pr["number"]) or merged_pr(number=400))
        self.assertEqual((resolved, read), ([400], [400]))

    def test_unread_stub_without_resolver_is_skipped_and_named(self):
        stub = {"number": 400, "state": "closed", "merged": True, "unread": True, "merged_at": "2026-10-01T10:00:00Z"}
        with self.assertRaisesRegex(workers.WorkerError, "PR #400.*no resolve_pr"):
            self.run_next([stub])

    def test_idle_run_derives_and_settles_every_candidate(self):
        def done(n):
            return [record("merged", attempts={"post-merge": 1}, number=n),
                    receipt("retrospective", 0, "task-recorded", 2, number=n),
                    receipt("terminal-reconciliation", 0, "ok", 3, number=n), receipt("cleanup", 0, "cleaned", 4, number=n)]
        settled, read = [], []
        result = workers.work_next(
            self.KINDS, list_prs=lambda: [merged_pr(number=n, merged_at=f"2026-10-2{n}T10:00:00Z") for n in (1, 2, 3)],
            comments_for=lambda n: read.append(n) or done(n),
            post_comment=lambda n, body: None, worker="w", settle=settled.append,
            trusted_apps=frozenset(), trusted_writers=frozenset())
        self.assertEqual((result["status"], read, settled), ("idle", [3, 2, 1], [3, 2, 1]))

    def test_merged_pr_without_merged_at_fails_the_run(self):
        with self.assertRaisesRegex(workers.WorkerError, "PR #7 has no readable merged_at"):
            self.run_next([{**merged_pr(), "merged_at": None}])

    def test_other_kinds_keep_ascending_order(self):
        order = workers.offer_order(frozenset({"review"}))
        prs = [{"number": 9, "state": "open"}, {"number": 3, "state": "open"}]
        self.assertEqual([pr["number"] for pr in sorted(prs, key=order)], [3, 9])


class CompositionPostMergeRetrospectiveTests(unittest.TestCase):
    """BR-950: the merged composition's post-merge retrospective job is the only Requirement checkpoint."""

    def test_composition_retrospective_records_the_requirement_checkpoint_after_every_child(self):
        identity = {"kind": "requirement-composition", "requirement": "pln_x", "task_content": {"digest": "d"},
                    "children": [{"change": "first"}]}
        job = {"kind": "retrospective", "number": 11, "head": HEAD, "task_identity": identity, "attempt": 0}
        candidate = {"number": 11, "head": HEAD, "state": "merged", "task_identity": identity}
        manifest = {"children": [{"pr_number": 5, "source_branch": "agent/br-7-t1-first", "head": "b" * 40}]}
        exact = {"requirement": "acme/backlog#7", "children": [{"source_issue": "acme/backlog#8"}]}
        calls, posted = [], []
        import requirement_composition
        import requirement_contributions
        with mock.patch.object(workers, "build_job", return_value=job), \
                mock.patch.object(workers, "prepare_checkout", return_value=Path("/c")), \
                mock.patch.object(requirement_composition, "candidate_manifest", return_value=manifest), \
                mock.patch.object(requirement_contributions, "private_manifest", return_value=exact), \
                mock.patch.object(contour, "run_retrospective", side_effect=lambda ops, root, n, b, h: calls.append(n) or "task-recorded"), \
                mock.patch.object(contour, "ensure_requirement_checkpoint") as checkpoint:
            ops = mock.Mock()
            result = contour.run_claimed_post_merge(Path("/root"), "o/r", candidate, job, branch="requirement/BR-7",
                                                    post_result=posted.append, ops=ops, worker="w", claim_current=lambda: True)
        self.assertEqual(calls, [5, 11])
        checkpoint.assert_called_once_with(ops, Path("/root"), "acme/backlog#7", ["acme/backlog#8"])
        self.assertEqual(result, {"status": "done", "outcome": "task-and-requirement-recorded"})


LIFECYCLE_START = "2000-01-01T00:00:00+00:00"


class FakeOps(contour.LifecycleOps):
    def __init__(self, *, closed=(), lineage=None, started=LIFECYCLE_START):
        self.closed, self._lineage = set(closed), lineage or {"requirement": REQUIREMENT, "child": CHILDREN[0]}
        self.started = started
        self.calls = []
        self.checkpointed = False
        self.cleanup_result = {"status": "cleaned", "removed": ["/w/x"], "errors": []}

    def lineage(self, root, branch):
        return self._lineage

    def requirement_started_at(self, root, requirement):
        return friction.parse_time(self.started)

    def candidate_admitted_at(self, root, number):
        return friction.parse_time(self.started)

    def children(self, root, requirement):
        return list(CHILDREN)

    def child_closed(self, root, child):
        return child in self.closed

    def reconcile_child(self, root, child):
        self.calls.append(("child", child))
        self.closed.add(child)

    def requirement_checkpoint(self, root, requirement, event_ids):
        self.calls.append(("requirement-checkpoint", tuple(event_ids)))
        self.checkpointed = True

    def requirement_checkpointed(self, root, requirement):
        return self.checkpointed

    def reconcile_parent(self, root, requirement, merged_children):
        self.calls.append(("parent", requirement))

    def cleanup(self, root, branch, number, merged_head):
        self.calls.append(("cleanup", branch))
        return self.cleanup_result


class FrictionFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude/agent-friction.jsonl"
        self.state = self.root / ".claude/agent-friction-state.json"
        self.log.parent.mkdir(parents=True)
        for patch in (mock.patch.object(friction, "log_path", lambda: self.log),
                      mock.patch.object(friction, "state_path", lambda: self.state),
                      mock.patch.object(friction, "current_branch", lambda: "main")):
            patch.start()
            self.addCleanup(patch.stop)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def record(self, key="k1", **kw):
        values = dict(task="agent/br-7-t8-task", requirement=REQUIREMENT, category="coordinator-retry",
                      triggers=["excessive-retry"], severity="medium", observation="obs", evidence="ev",
                      hypothesis="hyp", proposal="prop", dedupe_key=key, reason="review: provider-unavailable",
                      candidate={"task": "agent/br-7-t8-task", "number": 8, "head": HEAD})
        return friction.append_coordinator_event(**{**values, **kw})


class FrictionAttributionTests(FrictionFixture):
    def task_less(self, event_id):
        with self.log.open("a") as handle:
            handle.write(json.dumps({"id": event_id, "at": friction.utc_now(), "category": "x",
                                     "severity": "medium", "triggers": ["excessive-retry"]}) + "\n")

    def test_attribution_is_append_only_and_resolves_ambiguity(self):
        self.task_less("e1")
        before = self.log.read_bytes()
        self.assertEqual([e["id"] for e in friction.ambiguous_attribution_events()], ["e1"])
        record = friction.attribute_event("e1", "acme/backlog#5", "observation names that Requirement")
        self.assertEqual((record["id"], record["task"]), ("e1", "acme/backlog#5"))
        self.assertEqual(self.log.read_bytes(), before)
        self.assertEqual(friction.ambiguous_attribution_events(), [])
        self.assertIn("e1", [e["id"] for e in friction.events_for_task("acme/backlog#5")])
        self.assertEqual(friction.attribute_event("e1", "acme/backlog#5", "again"), record)
        self.assertEqual(len(friction.attributions_path().read_text().splitlines()), 1)

    def test_attribution_refuses_unknown_events_conflicts_and_malformed_input(self):
        self.task_less("e1")
        with self.assertRaisesRegex(SystemExit, "no recorded friction event"):
            friction.attribute_event("missing", "acme/backlog#5", "reason")
        friction.attribute_event("e1", "acme/backlog#5", "reason")
        with self.assertRaisesRegex(SystemExit, "already attributed to acme/backlog#5"):
            friction.attribute_event("e1", "acme/backlog#6", "reason")
        with self.assertRaisesRegex(SystemExit, "owner/repo#N"):
            friction.attribute_event("e1", "BR-5", "reason")
        with self.assertRaises(SystemExit):
            friction.attribute_event("e1", "acme/backlog#5", "   ")
        self.assertEqual(len(friction.attributions_path().read_text().splitlines()), 1)

    def test_conflicting_attribution_records_fail_when_read(self):
        friction.attributions_path().write_text(
            json.dumps({"id": "e1", "task": "acme/backlog#5"}) + "\n" + json.dumps({"id": "e1", "task": "acme/backlog#6"}) + "\n")
        with self.assertRaisesRegex(SystemExit, "Conflicting friction attributions"):
            friction.read_attributions()

    def test_coordinator_event_carries_task_and_requirement_and_is_recorded_once(self):
        first = self.record()
        again = self.record()
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(len(self.events()), 1)
        event = self.events()[0]
        self.assertEqual((event["task"], event["requirement"]), ("agent/br-7-t8-task", REQUIREMENT))
        self.assertIn(first["id"], [e["id"] for e in friction.events_for_task(REQUIREMENT)])
        self.assertIn(first["id"], [e["id"] for e in friction.events_for_task("agent/br-7-t8-task")])

    def test_lifecycle_transitions_record_friction_through_the_registered_sink(self):
        with Multi({7: HEAD}) as multi:
            queue.set_friction_sink(contour.default_friction_sink(ROOT), worker="test-worker")
            self.addCleanup(queue.set_friction_sink, None)
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity={"head": "x"},
                              red_gate={"name": "review", "evidence": "material findings unresolved"})
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity={"head": "x"},
                              red_gate={"name": "review", "evidence": "material findings unresolved"})
            events = self.events()
            self.assertEqual(len(events), 1)
            self.assertEqual((events[0]["task"], events[0]["work_identity"]), ("agent/br-7-t7-task", "BR-7"))
            self.assertEqual(events[0]["category"], "lifecycle-blocked-escalation")

    def test_composition_friction_lineage_is_selected_by_premerge_requirement_checkpoint(self):
        import managed_task
        with mock.patch.object(managed_task, "authoring_config", return_value=SimpleNamespace(repository="acme/backlog")):
            self.assertEqual(contour.resolve_lineage(self.root, "requirement/BR-7"),
                             {"requirement": REQUIREMENT, "child": None})
            sink = contour.default_friction_sink(self.root)
            with mock.patch.object(queue, "post_evidence", return_value={"event_id": "coordinator-0123456789abcdef"}):
                sink({"task": "requirement/BR-7", "category": "coordinator-retry", "severity": "medium",
                      "triggers": ["excessive-retry"], "observation": "retry", "evidence": "repair",
                      "hypothesis": "h", "proposal": "p", "dedupe_key": "composition-retry",
                      "reason": "repair: provider-unavailable", "number": 9, "head": HEAD})
        event = self.events()[0]
        self.assertEqual((event["requirement"], event["work_identity"]), (None, "BR-7"))
        ops = FakeOps()
        contour.ensure_requirement_checkpoint(ops, self.root, REQUIREMENT, CHILDREN)
        self.assertEqual(ops.calls, [("requirement-checkpoint", (event["id"],))])

    def test_friction_failure_prevents_transition_and_retry_records_event_before_handoff(self):
        with Multi({7: HEAD}) as multi:
            multi.ready(7)
            before = list(multi.comments[7])
            sink = mock.Mock(side_effect=OSError("friction storage denied"))
            queue.set_friction_sink(sink, worker="test-worker")
            self.addCleanup(queue.set_friction_sink, None)
            for failure in (OSError("friction storage denied"), SystemExit("invalid lineage")):
                sink.side_effect = failure
                with self.assertRaisesRegex(queue.QueueError, "friction recording failed.*retry transition"):
                    queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity={"head": "x"},
                                      red_gate={"name": "review", "evidence": "material findings"})
                self.assertEqual(multi.comments[7], before)
            sink.side_effect = contour.default_friction_sink(self.root)
            result = queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity={"head": "x"},
                                       red_gate={"name": "review", "evidence": "material findings"})
            self.assertEqual(result["state"], "repair-pending")
            self.assertEqual(len(self.events()), 1)

    def test_no_sink_means_no_friction_log(self):
        queue.set_friction_sink(None)
        with Multi({7: HEAD}) as multi:
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity={"head": "x"})
        self.assertEqual(self.events(), [])

    def test_child_attributed_event_is_accepted_by_the_requirement_retrospective(self):
        parent = {"body": "## Outcome\n\nX\n\n## Target repository\n\n`acme/project`\n\n"
                          "<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n- [ ] acme/backlog#9\n"
                          "<!-- requirement-children:end -->"}
        events = [{"id": "child", "task": CHILDREN[0], "observation": "retry"},
                  {"id": "stranger", "task": "acme/backlog#99", "observation": "other"}]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent), \
                mock.patch.object(retrospective.agent_friction, "read_events", return_value=events):
            result = retrospective.checkpoint(Path(tmp), requirement=REQUIREMENT, result="findings",
                                              event_ids=["child"], review_note="Reviewed the Requirement path.")
            self.assertEqual(result["event_ids"], ["child"])  # accepted without re-recording
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "not attributed"):
                retrospective.checkpoint(Path(tmp), requirement=REQUIREMENT, result="findings",
                                         event_ids=["stranger"], review_note="Reviewed the Requirement path.")


class PostMergeJobTests(FrictionFixture):
    branch = "agent/br-7-t8-task"

    def run_job(self, kind, ops, *, attempt=0):
        merged = lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1})])
        job = {"number": 7, "kind": kind, "head": HEAD, "task_identity": merged["task_identity"], "attempt": attempt}
        posted = []
        with mock.patch.object(workers, "build_job", return_value=job):
            outcome = contour.run_claimed_post_merge(
                ROOT, "o/r", merged, job, branch=self.branch, post_result=posted.append, ops=ops,
                claim_current=lambda: True, worker="w")
        return outcome, posted

    def test_retrospective_links_recorded_events_instead_of_inventing_none(self):
        event = self.record(task=self.branch)
        outcome, posted = self.run_job("retrospective", FakeOps(closed=[CHILDREN[1]]))
        self.assertEqual(outcome["status"], "done")
        checkpoint = json.loads(self.state.read_text())["checkpoints"][self.branch]
        self.assertEqual(checkpoint["event_ids"], [event["id"]])
        self.assertIn("task-and-requirement-recorded", outcome["outcome"])
        self.assertEqual(len(posted), 1)

    def test_clean_path_records_none_and_defers_the_requirement_until_children_are_delivered(self):
        ops = FakeOps()
        outcome, _ = self.run_job("retrospective", ops)
        self.assertEqual(json.loads(self.state.read_text())["checkpoints"][self.branch]["result"], "none")
        self.assertIn("awaits remaining children", outcome["outcome"])
        self.assertEqual(ops.calls, [])

    def test_ambiguous_attribution_blocks_instead_of_recording_none(self):
        self.log.write_text(json.dumps({"id": "amb", "at": friction.utc_now(), "category": "x", "severity": "medium",
                                        "triggers": ["excessive-retry"]}) + "\n")
        outcome, posted = self.run_job("retrospective", FakeOps())
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("ambiguous", posted[0])
        self.assertFalse(self.state.exists())

    def unattributed(self, event_id, at):
        with self.log.open("a") as handle:
            handle.write(json.dumps({"id": event_id, "at": at, "category": "x", "severity": "medium",
                                     "triggers": ["excessive-retry"]}) + "\n")

    def test_unattributed_event_before_admission_does_not_block_the_candidate(self):
        self.unattributed("older", WINDOW_OLDER)
        outcome, posted = self.run_job("retrospective", FakeOps(started=WINDOW_STARTED))
        self.assertNotEqual(outcome["status"], "blocked")
        self.assertNotIn("ambiguous", posted[0])

    def test_unattributed_event_after_admission_still_blocks(self):
        self.unattributed("older", WINDOW_OLDER)
        self.unattributed("inside", WINDOW_INSIDE)
        outcome, posted = self.run_job("retrospective", FakeOps(started=WINDOW_STARTED))
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("inside", posted[0])
        self.assertNotIn("older", posted[0])

    def test_event_recorded_outside_a_task_does_not_block_another_candidate(self):
        with self.log.open("a") as handle:
            handle.write(json.dumps({"id": "elsewhere", "at": WINDOW_INSIDE, "branch": "main", "task": None,
                                     "attribution": "no-task", "category": "x", "severity": "medium",
                                     "triggers": ["excessive-retry"]}) + "\n")
        outcome, posted = self.run_job("retrospective", FakeOps(started=WINDOW_STARTED))
        self.assertNotEqual(outcome["status"], "blocked")
        self.assertNotIn("elsewhere", posted[0])
        self.assertEqual(json.loads(self.state.read_text())["checkpoints"][self.branch]["event_ids"], [])

    def test_requirement_window_starts_at_its_creation(self):
        self.unattributed("older", WINDOW_OLDER)
        ops = FakeOps(started=WINDOW_STARTED)
        contour.ensure_requirement_checkpoint(ops, self.root, REQUIREMENT, CHILDREN)
        self.assertEqual(ops.calls, [("requirement-checkpoint", ())])
        self.unattributed("inside", WINDOW_INSIDE)
        with self.assertRaisesRegex(contour.JobBlocked, "ambiguous friction attribution.*inside"):
            contour.ensure_requirement_checkpoint(ops, self.root, REQUIREMENT, CHILDREN)

    def test_unknown_lifecycle_start_blocks_explicitly(self):
        import managed_task
        with mock.patch.object(managed_task, "fetch_issue", return_value={}):
            with self.assertRaisesRegex(contour.JobBlocked, "cannot prove when acme/backlog#7 started"):
                contour.LifecycleOps().requirement_started_at(self.root, REQUIREMENT)
        with mock.patch.object(managed_task, "fetch_issue", side_effect=managed_task.ManagedTaskError("no gh")):
            with self.assertRaisesRegex(contour.JobBlocked, "cannot prove when acme/backlog#7 started: no gh"):
                contour.LifecycleOps().requirement_started_at(self.root, REQUIREMENT)
        with mock.patch.object(managed_task, "fetch_issue", return_value={"created_at": "2026-10-02T00:00:00Z"}) as fetch:
            self.assertEqual(contour.LifecycleOps().requirement_started_at(self.root, REQUIREMENT),
                             friction.parse_time("2026-10-02T00:00:00+00:00"))
        self.assertEqual(fetch.call_args.args[1:], ("acme/backlog", 7))
        with mock.patch.object(queue, "_repo", return_value="o/r"), mock.patch.object(queue, "_comments", return_value=[]), \
                mock.patch.object(queue, "trusted_apps", return_value=frozenset()), \
                mock.patch.object(queue, "trusted_writers", return_value=frozenset()):
            with self.assertRaisesRegex(contour.JobBlocked, "cannot prove when PR #7 was admitted"):
                contour.LifecycleOps().candidate_admitted_at(self.root, 7)

    def test_malformed_first_record_blocks_the_admission_proof_naming_the_comment(self):
        broken = {"id": 77, "author_association": "OWNER", "body": "dev-platform-publication-queue:v2 {broken"}
        with mock.patch.object(queue, "_repo", return_value="o/r"), mock.patch.object(queue, "_comments", return_value=[broken]), \
                mock.patch.object(queue, "trusted_apps", return_value=frozenset()), \
                mock.patch.object(queue, "trusted_writers", return_value=frozenset()):
            with self.assertRaisesRegex(contour.JobBlocked, "cannot prove when PR #7 was admitted: malformed marker comment 77"):
                contour.LifecycleOps().candidate_admitted_at(self.root, 7)

    def test_unreadable_friction_log_is_not_a_clean_result(self):
        self.log.write_text("{broken\n")
        outcome, _ = self.run_job("retrospective", FakeOps())
        self.assertEqual(outcome["status"], "blocked")

    def test_terminal_reconciliation_closes_child_then_parent_once_all_children_are_done(self):
        ops = FakeOps(closed=[CHILDREN[1]])
        outcome, _ = self.run_job("terminal-reconciliation", ops)
        self.assertEqual(outcome["outcome"], "requirement-reconciled")
        self.assertEqual([c[0] for c in ops.calls], ["child", "requirement-checkpoint", "parent"])
        rerun = FakeOps(closed=[CHILDREN[0], CHILDREN[1]])
        rerun.checkpointed = True
        self.run_job("terminal-reconciliation", rerun)
        self.assertEqual([c[0] for c in rerun.calls], ["child", "parent"])  # idempotent re-run

    def test_terminal_reconciliation_waits_for_remaining_children(self):
        ops = FakeOps()
        outcome, _ = self.run_job("terminal-reconciliation", ops)
        self.assertIn("awaits remaining children", outcome["outcome"])
        self.assertEqual([c[0] for c in ops.calls], ["child"])

    def test_unresolvable_source_issue_is_blocked_not_guessed(self):
        outcome, _ = self.run_job("terminal-reconciliation", FakeOps(lineage={"requirement": None, "child": None}))
        self.assertEqual(outcome["status"], "blocked")

    def test_a_quick_task_without_lineage_completes_and_the_queue_reaches_the_next_job(self):
        ops = FakeOps()
        ops._lineage = None  # a quick-task branch carries no BR identity
        outcome, posted = self.run_job("terminal-reconciliation", ops)
        self.assertEqual((outcome["status"], outcome["outcome"]), ("done", "no-source-issue: quick task"))
        self.assertEqual(ops.calls, [])
        rows = [record("merged", attempts={"post-merge": 1}), receipt("retrospective", 0, "task-recorded", 2),
                receipt("terminal-reconciliation", 0, outcome["outcome"], 3)]
        self.assertEqual(lifecycle.derive_candidate(merged_pr(), rows)["next_job"]["kind"], "cleanup")

    def test_a_managed_candidate_that_lost_its_lineage_stays_blocked(self):
        ops = FakeOps()
        ops._lineage = None
        merged = lifecycle.derive_candidate(merged_pr(), [record(
            "merged", attempts={"post-merge": 1}, identity={"change": "managed-change", "task_content": {"digest": "d"}})])
        job = {"number": 7, "kind": "terminal-reconciliation", "head": HEAD, "task_identity": merged["task_identity"], "attempt": 0}
        with mock.patch.object(workers, "build_job", return_value=job):
            outcome = contour.run_claimed_post_merge(ROOT, "o/r", merged, job, branch="agent/managed-change",
                                                     post_result=lambda body: None, ops=ops,
                                                     claim_current=lambda: True, worker="w")
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("cannot resolve the task's source Issue", outcome["outcome"])

    def test_operator_errors_are_failed_receipts_that_get_retried(self):
        ops = FakeOps()
        ops.reconcile_child = mock.Mock(side_effect=RuntimeError("no GitHub authentication"))
        outcome, posted = self.run_job("terminal-reconciliation", ops)
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("failed: no GitHub authentication", posted[0])

    def test_cleanup_reports_removed_clean_and_refused_states(self):
        ops = FakeOps()
        self.assertEqual(self.run_job("cleanup", ops)[0]["outcome"], "cleaned")
        ops.cleanup_result = {"status": "already-clean", "removed": [], "errors": []}
        self.assertEqual(self.run_job("cleanup", ops)[0]["outcome"], "already-clean")
        ops.cleanup_result = {"status": "blocked", "removed": [], "errors": [{"path": "/w/x", "error": "dirty"}]}
        outcome, _ = self.run_job("cleanup", ops)
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("dirty", outcome["outcome"])

    def test_an_unavailable_process_check_fails_the_run_without_a_receipt(self):
        ops = FakeOps()
        ops.cleanup_result = {"status": "blocked", "removed": [],
                              "errors": [{"path": "/w/x", "error": "process-check-unavailable"}]}
        merged = lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1})])
        job = {"number": 7, "kind": "cleanup", "head": HEAD, "task_identity": merged["task_identity"], "attempt": 0}
        posted = []
        with mock.patch.object(workers, "build_job", return_value=job):
            with self.assertRaisesRegex(contour.PostMergeEnvironmentError,
                                        "process-check-unavailable.*no attempt was recorded"):
                contour.run_claimed_post_merge(ROOT, "o/r", merged, job, branch=self.branch, post_result=posted.append,
                                               ops=ops, claim_current=lambda: True, worker="w")
        self.assertEqual(posted, [])  # no receipt: the attempt counter is unchanged
        self.assertTrue(issubclass(contour.PostMergeEnvironmentError, workers.WorkerError))

    def test_a_job_for_a_stale_candidate_is_discarded(self):
        merged = lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1})])
        job = {**workers.build_job(merged), "attempt": 5}
        outcome = contour.run_claimed_post_merge(ROOT, "o/r", merged, job, branch=self.branch,
                                                 post_result=lambda body: self.fail("no receipt"), ops=FakeOps(),
                                                 claim_current=lambda: True, worker="w")
        self.assertEqual(outcome["status"], "discarded")


class LocalCleanupTests(unittest.TestCase):
    def worktree(self, path="/managed/w1", head="1" * 40):
        return SimpleNamespace(path=Path(path), head=head, branch="agent/br-7-t8-task")

    def run_cleanup(self, worktrees, *, ancestor, managed="/managed", target_result=None):
        import worktree_cleanup as cleanup

        calls = []

        def run_git(args, **kwargs):
            calls.append(args[0])
            if args[0] == "rev-parse":
                return SimpleNamespace(stdout=HEAD + "\n", returncode=0)
            return SimpleNamespace(stdout="", returncode=0 if ancestor else 1)

        with mock.patch.object(cleanup, "_list_worktrees", return_value=worktrees), \
                mock.patch("_platform_common.run_git", side_effect=run_git), \
                mock.patch("_platform_common.machine_path", return_value=Path(managed)), \
                mock.patch.object(cleanup, "defer_completed_task", return_value=(Path("/x"), "target")) as defer, \
                mock.patch.object(cleanup, "_cleanup_target",
                                  return_value=target_result or {"removed": ["/managed/w1"], "errors": []}) as target:
            return contour.local_cleanup(ROOT, "agent/br-7-t8-task", 7, HEAD), defer, target

    def test_no_local_worktree_is_already_clean(self):
        result, defer, _ = self.run_cleanup([], ancestor=True)
        self.assertEqual(result["status"], "already-clean")
        defer.assert_not_called()

    def test_delivered_worktree_is_removed_through_the_exact_target_path(self):
        result, defer, target = self.run_cleanup([self.worktree()], ancestor=True)
        self.assertEqual((result["status"], result["removed"]), ("cleaned", ["/managed/w1"]))
        target.assert_called_once()

    def test_commits_missing_from_the_merged_pr_and_foreign_paths_are_refused(self):
        result, defer, _ = self.run_cleanup([self.worktree()], ancestor=False)
        self.assertEqual(result["errors"][0]["error"], "local-commits-not-in-merged-pr")
        result, defer, _ = self.run_cleanup([self.worktree("/elsewhere/w")], ancestor=True)
        self.assertEqual(result["errors"][0]["error"], "outside-managed-directory")
        defer.assert_not_called()

    def test_dirty_or_active_state_reported_by_the_cleanup_target_is_surfaced(self):
        result, _, _ = self.run_cleanup([self.worktree()], ancestor=True,
                                        target_result={"removed": [], "errors": [{"path": "/managed/w1", "error": "dirty"}]})
        self.assertEqual(result["status"], "blocked")


class LineageTests(unittest.TestCase):
    def test_branch_identity_resolves_requirement_and_child_or_nothing(self):
        self.assertIsNone(contour.resolve_lineage(ROOT, "agent/example"))
        body = "<!-- br-child:acme/backlog#8:6 -->\n"
        with mock.patch("managed_task.authoring_config", return_value=SimpleNamespace(repository="acme/backlog")), \
                mock.patch("requirement_intake.fetch_issue", return_value={"body": body}):
            self.assertEqual(contour.resolve_lineage(ROOT, "agent/br-7-t6-change"),
                             {"requirement": "acme/backlog#7", "child": "acme/backlog#8"})
        with mock.patch("managed_task.authoring_config", side_effect=RuntimeError("no config")):
            with self.assertRaisesRegex(RuntimeError, "no config"):
                contour.resolve_lineage(ROOT, "agent/br-7-t6-change")



def released(job_kind, attempt, row_id, cause="RuntimeError: boom"):
    job = {"number": 7, "kind": job_kind, "head": HEAD, "attempt": attempt}
    return {"id": row_id, "author_association": "OWNER",
            "body": workers.result_body(job, f"w{row_id}", f"{workers.RELEASED}: {cause}")}


class PostMergeReleaseLimitTests(unittest.TestCase):
    """BR-775: a post-merge job released MAX_RELEASES times raises attention instead of stopping silently."""

    def derive(self, *rows):
        return lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1}), *rows])

    def test_job_is_offered_until_the_release_limit_then_counts_as_exhausted(self):
        rows = [released("retrospective", 0, 10 + n) for n in range(workers.MAX_RELEASES - 1)]
        self.assertEqual(self.derive(*rows)["next_job"]["kind"], "retrospective")
        rows.append(released("retrospective", 0, 20, cause="RuntimeError: last cause"))
        spent = self.derive(*rows)
        self.assertIsNone(spent["next_job"])
        self.assertEqual(spent["post_merge_exhausted"], "retrospective")
        self.assertEqual(spent["post_merge_released"], {"kind": "retrospective", "attempt": 0,
                                                        "releases": workers.MAX_RELEASES,
                                                        "last": "released: RuntimeError: last cause"})
        self.assertTrue(spent["reason"].startswith("post-merge retrospective exhausted 3 claim releases"))
        self.assertIn("last cause", spent["reason"])
        self.assertEqual(lifecycle.post_merge_job(spent, [record("merged", attempts={"post-merge": 1}), *rows])[0], None)

    def test_attention_names_the_releases_and_the_reoffer_command(self):
        rows = [released("cleanup", 0, 10 + n) for n in range(workers.MAX_RELEASES)]
        done = [receipt("retrospective", 0, "task-recorded", 2), receipt("terminal-reconciliation", 0, "ok", 3)]
        comments = [record("merged", attempts={"post-merge": 1}), *done, *rows]
        candidate = lifecycle.derive_candidate(merged_pr(), comments)
        plan = gate.permitted_post_merge_actions(candidate, comments, number=7)
        self.assertEqual([item["action"] for item in plan["actions"]], ["reoffer-post-merge"])
        self.assertIn("claim released 3 times: released: RuntimeError: boom", plan["human_decision"])
        body = queue.attention_body("o/r", 7, candidate, None, plan)
        self.assertIn("exhausted 3 claim releases", body)
        self.assertIn("reoffer-post-merge --pr 7", body)

    def test_reoffer_gives_a_released_job_a_fresh_budget(self):
        rows = [released("retrospective", 0, 10 + n) for n in range(workers.MAX_RELEASES)]
        event = {"seq": 1, "action": "reoffer-post-merge", "kind": "retrospective", "reason": "fixed",
                 "actor": "o", "head": HEAD, "at": "2026-10-30T00:00:00Z"}
        reoffered = lifecycle.marker_body(lifecycle.build_handoff_record(
            number=7, state="merged", head=HEAD, task_identity={"branch": "agent/br-7-t8-task", "head": HEAD},
            gates={}, red_gate=None, not_reverified=[], attempts={"post-merge": 1, "post-merge-reoffers": 1},
            next_job=workers.job_record("retrospective", HEAD, {"branch": "agent/br-7-t8-task", "head": HEAD}, 0,
                                        reoffer=event),
            at="2026-10-30T00:00:00+00:00"))
        candidate = lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1}), *rows,
                                                             {"id": 90, "author_association": "OWNER", "body": reoffered}])
        self.assertEqual((candidate["next_job"]["kind"], candidate["next_job"]["reoffer"]["seq"]), ("retrospective", 1))
        self.assertNotIn("post_merge_exhausted", candidate)

    def test_third_release_of_a_post_merge_run_posts_the_attention(self):
        store = [record("merged", attempts={"post-merge": 1})]

        def gh(*args):
            if args[1] == "repos/o/r/issues/7/comments" and "-f" in args:
                store.append({"id": 100 + len(store), "author_association": "OWNER", "body": args[-1][len("body="):]})
                return {}
            if "issues/7/comments" in args[-1]:
                return list(store)
            if args[-1] == "repos/o/r/pulls/7":
                return {"head": {"sha": HEAD, "ref": "agent/br-7-t8-task"}, "merged": True}
            raise AssertionError(args)
        fake_queue = mock.Mock()
        argv = ["work-next", "--kinds", "retrospective", "--repo", "o/r", "--run", "--worker", "w"]
        with mock.patch.object(workers, "_gh_json", side_effect=gh), \
                mock.patch.object(workers, "candidate_prs", return_value=[merged_pr()]), \
                mock.patch.object(workers, "_coordinator_trust", return_value={"trusted_apps": frozenset(), "trusted_writers": frozenset()}), \
                mock.patch.object(contour, "run_claimed_post_merge", side_effect=RuntimeError("boom")), \
                mock.patch.dict(sys.modules, {"publication_queue": fake_queue, "integration_contour": contour}):
            for attempt in range(1, workers.MAX_RELEASES + 1):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    workers.main(argv)
                self.assertEqual(fake_queue.ensure_post_merge_attention.called, attempt == workers.MAX_RELEASES)
        fake_queue.ensure_post_merge_attention.assert_called_once_with(mock.ANY, "o/r", 7)
        fake_queue._transition.assert_not_called()  # a merged PR never moves to blocked-escalation

if __name__ == "__main__":
    unittest.main()
