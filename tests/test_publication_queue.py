from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import publication_queue as queue  # noqa: E402
from publication_state import RequiredCheckState  # noqa: E402

BASE = "a" * 40
HEAD = "b" * 40
NEW_HEAD = "c" * 40
REPO = "owner/repo"
ROOT_PATH = Path("/unused")


def setUpModule() -> None:
    # Finalization of the exact PR head is covered by test_post_review_finalization.
    patcher = patch.object(queue, "_require_finalized")
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


def admission(number: int, key: int, head: str = HEAD) -> dict:
    return {"version": 1, "number": number, "kind": "admit", "comment_id": key,
            "head": head, "base": BASE, "branch": f"agent/{number}"}


def pr(number: int, head: str = HEAD, labels: tuple[str, ...] = ()) -> dict:
    return {"number": number, "state": "open", "merged": False,
            "base": {"ref": "main"}, "head": {"ref": f"agent/{number}", "sha": head},
            "labels": [{"name": label} for label in labels]}


class AdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        # v2 handoff publication is covered by TransitionRecordTests; keep the
        # v1 queue scenarios focused on admission and merge ordering.
        patcher = patch.object(queue, "_transition")
        self.transition = patcher.start()
        self.addCleanup(patcher.stop)
        comments = patch.object(queue, "_comments", return_value=[])
        comments.start()
        self.addCleanup(comments.stop)
        handoff = patch.object(queue, "_admission_handoff", return_value={"task_identity": {"head": HEAD}, "gates": {}})
        handoff.start()
        self.addCleanup(handoff.stop)

    def test_refreshed_contribution_handoff_readmits_only_semantic_stop_same_candidate(self):
        old = {"kind": "contribution", "change": "first", "requirement": "owner/backlog#7",
               "source_issue": "owner/backlog#8", "target_branch": "requirement/BR-7",
               "contribution_base": BASE, "task_content": {"digest": "old"}}
        identity = {**old, "task_content": {"digest": "repaired"}}
        handoff = {"task_identity": identity, "gates": {g: {"result": "passed", "identity": identity,
                   "evidence": {"receipt": "fresh"}} for g in ("developer-friction", "selected-checks", "semantic-verification")}}
        handoff["gates"]["developer-friction"]["evidence"]["head"] = NEW_HEAD
        prior = {"head": HEAD, "state": "blocked-retryable", "task_identity": old,
                 "red_gate": {"name": "semantic-verification", "identity": old}}
        observed = pr(1, NEW_HEAD); observed["base"]["ref"] = "requirement/BR-7"
        events = [admission(1, 17)]
        def comment(root, repo, number, payload):
            events.append({**payload, "comment_id": len(events) + 17})
        with patch.object(queue, "_repo", return_value=REPO), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_events", side_effect=lambda *a: list(events)), patch.object(queue, "_comment", side_effect=comment), \
             patch.object(queue, "_latest", return_value=prior), patch.object(queue, "_derive", return_value={}), \
             patch.object(queue, "_ensure_labels"), patch.object(queue, "_label"):
            for bad in ({**prior, "state": "reviewing"}, {**prior, "red_gate": {"name": "review", "identity": old}},
                        {**prior, "task_identity": {**old, "change": "different"}}):
                with patch.object(queue, "_latest", return_value=bad), self.assertRaisesRegex(queue.QueueError, "earlier or ambiguous"):
                    queue.admit(ROOT_PATH, 1, NEW_HEAD, handoff=handoff)
            # Return the refreshed review record for confirmation after the transition.
            def latest(root, number, comments, head=None):
                return {"head": NEW_HEAD, "state": "review-pending"} if head else prior
            with patch.object(queue, "_latest", side_effect=latest), patch.object(queue, "publish_job") as offer:
                result = queue.admit(ROOT_PATH, 1, NEW_HEAD, handoff=handoff)
            self.assertEqual(result["position_key"], 19)
            self.assertEqual([e["kind"] for e in events], ["admit", "block", "admit"])
            self.assertEqual(self.transition.call_args.args[3], "review-pending")
            offer.assert_called_once()

    def test_historical_pr_inventory_does_not_consume_queued_bound(self):
        history = [{"number": n, "labels": [], "state": "closed"} for n in range(150)]
        queued = [{"number": 151, "labels": [{"name": queue.QUEUE}], "state": "open"}]
        def gh(root, *args):
            self.assertEqual(args[args.index("--state") + 1], "all")
            self.assertEqual(args[args.index("--label") + 1], queue.QUEUE)
            return [r for r in history + queued if r["labels"]]
        with patch.object(queue, "_gh", side_effect=gh), patch.object(queue, "_events", return_value=[admission(151, 17)]):
            self.assertEqual(queue._queued(ROOT_PATH, REPO)[0][1], 151)
        with patch.object(queue, "_gh", return_value=queued * 100), self.assertRaisesRegex(queue.QueueError, "bounded limit"):
            queue._queued(ROOT_PATH, REPO)

    def test_concurrent_identical_admissions_reuse_oldest_slot(self) -> None:
        events = [admission(1, 19), admission(1, 17)]
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_events", return_value=events), \
             patch.object(queue, "_label") as label, \
             patch.object(queue, "_comment") as comment:
            result = queue.admit(ROOT_PATH, 1, HEAD)
        self.assertEqual(result["position_key"], 17)
        comment.assert_not_called()
        label.assert_called_once_with(ROOT_PATH, REPO, 1, queue.QUEUE, present=True)

    def test_composition_admission_uses_validated_composition_provenance(self) -> None:
        observed = pr(1)
        observed["head"]["ref"] = "requirement/BR-415"
        identity = {"kind": "requirement-composition", "requirement": "owner/repo#415",
                    "task_content": {"digest": "composition-proof"}}
        gates = {"finalization": {"result": "passed", "identity": identity}}
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_latest", return_value={"task_identity": identity}), \
             patch.object(queue, "_derive", return_value={"head": HEAD, "task_identity": None}), \
             patch.object(queue, "_events", return_value=[admission(1, 17)]), \
             patch.object(queue, "_label"), \
             patch.object(queue, "require_composition_finalized",
                          return_value={"task_identity": identity, "gates": gates}) as validate, \
             patch.object(queue, "_admission_handoff", side_effect=AssertionError("single-task proof requested")):
            result = queue.admit(ROOT_PATH, 1, HEAD)
        self.assertEqual(result["position_key"], 17)
        validate.assert_called_once_with(ROOT_PATH, REPO, 1, HEAD)
        self.assertEqual(self.transition.call_args.kwargs["task_identity"], identity)
        self.assertEqual(self.transition.call_args.kwargs["gates"], gates)

    def test_invalid_composition_provenance_stops_admission_before_mutation(self) -> None:
        observed = pr(1)
        observed["head"]["ref"] = "requirement/BR-415"
        identity = {"kind": "requirement-composition"}
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_latest", return_value={"task_identity": identity}), \
             patch.object(queue, "require_composition_finalized", side_effect=queue.QueueError("invalid final gates")), \
             patch.object(queue, "_comment") as comment, patch.object(queue, "_label") as label:
            with self.assertRaisesRegex(queue.QueueError, "invalid final gates"):
                queue.admit(ROOT_PATH, 1, HEAD)
        comment.assert_not_called()
        label.assert_not_called()
        self.transition.assert_not_called()

    def test_changed_head_cannot_reuse_prior_admission(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1, NEW_HEAD)), \
             patch.object(queue, "_events", return_value=[admission(1, 17)]):
            with self.assertRaisesRegex(queue.QueueError, "earlier or ambiguous"):
                queue.admit(ROOT_PATH, 1, NEW_HEAD)

    def test_corrected_head_gets_new_slot_after_block(self) -> None:
        old = admission(1, 17)
        blocked = {"kind": "block", "number": 1, "comment_id": 18, "reason": "failed check"}
        replacement = admission(1, 19, NEW_HEAD)
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1, NEW_HEAD)), \
             patch.object(queue, "_events", side_effect=[[old, blocked], [old, blocked, replacement]]), \
             patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "_ensure_labels"), \
             patch.object(queue, "_comment") as comment, \
             patch.object(queue, "_label") as label:
            result = queue.admit(ROOT_PATH, 1, NEW_HEAD)
        self.assertEqual(result["position_key"], 19)
        comment.assert_called_once()
        self.assertIn((ROOT_PATH, REPO, 1, queue.BLOCKED),
                      [call.args for call in label.call_args_list])

    def test_original_task_paths_survive_coordinator_branch_update(self) -> None:
        source = admission(1, 17)
        compare = {"files": [{"filename": "task.py"}]}
        with patch.object(queue, "_gh", return_value=compare) as gh:
            self.assertEqual(queue._task_paths(ROOT_PATH, REPO, source), {"task.py"})
        self.assertEqual(gh.call_args.args[-1], f"repos/{REPO}/compare/{BASE}...{HEAD}")

    def test_queue_order_and_owner_are_observable(self) -> None:
        rows = [{"number": 2, "labels": [{"name": queue.QUEUE}]},
                {"number": 1, "labels": [{"name": queue.QUEUE}]}]
        def events(_root: Path, _repo: str, number: int) -> list[dict]:
            return [admission(number, 30 if number == 2 else 20)]
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", side_effect=lambda _root, _repo, number: pr(number, labels=(queue.QUEUE,))), \
             patch.object(queue, "_gh", return_value=rows), \
             patch.object(queue, "_events", side_effect=events):
            self.assertEqual(queue.status(ROOT_PATH, 1)["state"], "waiting")
            self.assertEqual(queue.status(ROOT_PATH, 2)["position"], 2)
            self.assertEqual([item[1] for item in queue._queued(ROOT_PATH, REPO)], [1, 2])

    def test_active_owner_requires_coordinator_label(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1, labels=(queue.QUEUE, queue.ACTIVE))), \
             patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "_queued", return_value=[(20, 1, admission(1, 20))]):
            self.assertEqual(queue.status(ROOT_PATH, 1)["state"], "active")


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        # v2 handoff publication is covered by TransitionRecordTests; keep the
        # v1 queue scenarios focused on admission and merge ordering.
        patcher = patch.object(queue, "_transition")
        self.transition = patcher.start()
        self.addCleanup(patcher.stop)
        comments = patch.object(queue, "_comments", return_value=[])
        comments.start()
        self.addCleanup(comments.stop)
        handoff = patch.object(queue, "_admission_handoff", return_value={"task_identity": {"head": HEAD}, "gates": {}})
        handoff.start()
        self.addCleanup(handoff.stop)

    def test_two_admitted_agents_merge_in_order_on_successive_main_heads(self) -> None:
        from subprocess import CompletedProcess
        heads = {1: HEAD, 2: NEW_HEAD}
        prs = {number: pr(number, head) for number, head in heads.items()}
        comments: dict[int, list[dict]] = {1: [], 2: []}
        main = [BASE]
        next_comment = [10]
        prepared_bases: list[tuple[int, str]] = []

        def comment(_root: Path, _repo: str, number: int, payload: dict) -> None:
            comments[number].append({**payload, "comment_id": next_comment[0]})
            next_comment[0] += 1

        def label(_root: Path, _repo: str, number: int, name: str, *, present: bool) -> None:
            labels = prs[number]["labels"]
            labels[:] = [item for item in labels if item["name"] != name]
            if present:
                labels.append({"name": name})

        def gh(_root: Path, *args: str, **_kwargs: object) -> list[dict]:
            self.assertEqual(args[:2], ("pr", "list"))
            return [{"number": number, "labels": data["labels"]}
                    for number, data in prs.items() if not data["merged"]]

        def prepare(_root: Path, _repo: str, number: int, _admit: dict, _pr: dict) -> tuple[str, str]:
            prepared_bases.append((number, main[0]))
            return heads[number], main[0]

        def merge(args: list[str], **_kwargs: object) -> CompletedProcess[str]:
            self.assertEqual(args[:3], ["gh", "pr", "merge"])
            number = int(args[3])
            prs[number]["merged"] = True
            prs[number]["state"] = "closed"
            main[0] = heads[number]
            return CompletedProcess(args, 0, "merged", "")

        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", side_effect=lambda _root, _repo, number: prs[number]), \
             patch.object(queue, "_events", side_effect=lambda _root, _repo, number: comments[number]), \
             patch.object(queue, "_comment", side_effect=comment), \
             patch.object(queue, "_label", side_effect=label), \
             patch.object(queue, "_ensure_labels"), \
             patch.object(queue, "_main", side_effect=lambda _root: main[0]), \
             patch.object(queue, "_gh", side_effect=gh), \
             patch.object(queue, "_prepare", side_effect=prepare), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("passed")), \
             patch.object(queue.subprocess, "run", side_effect=merge):
            queue.admit(ROOT_PATH, 1, HEAD)
            queue.admit(ROOT_PATH, 2, NEW_HEAD)
            self.assertEqual(queue.status(ROOT_PATH, 2)["position"], 2)
            self.assertEqual(queue.worker(ROOT_PATH)["number"], 1)
            self.assertEqual(queue.worker(ROOT_PATH)["number"], 2)
            self.assertEqual(queue.worker(ROOT_PATH)["state"], "empty")
            self.assertEqual(queue.status(ROOT_PATH, 1)["state"], "merged")
            self.assertEqual(queue.status(ROOT_PATH, 2)["state"], "merged")
        self.assertEqual(prepared_bases, [(1, BASE), (2, HEAD)])
        self.assertEqual(len(comments[1]), 1)
        self.assertEqual(len(comments[2]), 1)

    def test_unrelated_main_advancement_prepares_new_head(self) -> None:
        from subprocess import CompletedProcess
        def git(args: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if args[0] == "diff":
                return CompletedProcess(args, 0, "other.py\n", "")
            if args[0] == "merge-base" and args[2] == NEW_HEAD:
                return CompletedProcess(args, 1, "", "")
            return CompletedProcess(args, 0, "", "")
        with patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "_main", return_value=NEW_HEAD), \
             patch.object(queue, "run_git", side_effect=git), \
             patch.object(queue, "_task_paths", return_value={"task.py"}), \
             patch.object(queue, "_gh") as gh, \
             patch.object(queue, "_pr", return_value=pr(1, NEW_HEAD)), \
             patch.object(queue, "_comment") as comment:
            self.assertEqual(queue._prepare(ROOT_PATH, REPO, 1, admission(1, 20), pr(1)),
                             (NEW_HEAD, NEW_HEAD))
        self.assertIn("update-branch", gh.call_args.args[-1])
        comment.assert_called_once()

    def test_runner_restart_proves_unrecorded_clean_branch_update(self) -> None:
        from subprocess import CompletedProcess
        tree = "d" * 40
        def git(args: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if args[0] == "rev-list":
                return CompletedProcess(args, 0, f"{NEW_HEAD} {HEAD} {BASE}\n", "")
            if args[0] == "merge-tree":
                return CompletedProcess(args, 0, tree + "\n", "")
            if args[0] == "rev-parse":
                return CompletedProcess(args, 0, tree + "\n", "")
            if args[0] == "diff":
                return CompletedProcess(args, 0, "", "")
            return CompletedProcess(args, 0, "", "")
        with patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "run_git", side_effect=git), \
             patch.object(queue, "_task_paths", return_value={"task.py"}), \
             patch.object(queue, "_comment") as comment:
            self.assertEqual(queue._prepare(ROOT_PATH, REPO, 1, admission(1, 20), pr(1, NEW_HEAD)),
                             (NEW_HEAD, BASE))
        self.assertEqual(comment.call_args.args[-1]["kind"], "update")

    def test_failed_required_check_becomes_integration_repair_before_merge(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(20, 1, admission(1, 20))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_label"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("failed", "validate")), \
             patch.object(queue, "_integration_repair", return_value={"state": "waiting", "number": 1}) as repair, \
             patch.object(queue, "_block", return_value={"state": "blocked"}) as block, \
             patch.object(queue.subprocess, "run") as process:
            self.assertEqual(queue.worker(ROOT_PATH)["state"], "waiting")
        block.assert_not_called()
        self.assertEqual(repair.call_args.args[-1].gate, "required-checks")
        process.assert_not_called()

    def test_main_movement_prevents_merge_under_old_evidence(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(20, 1, admission(1, 20))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_label"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("passed")), \
             patch.object(queue, "_main", return_value=NEW_HEAD), \
             patch.object(queue.subprocess, "run") as process:
            self.assertEqual(queue.worker(ROOT_PATH)["state"], "waiting")
        process.assert_not_called()

    def test_external_head_change_is_blocked(self) -> None:
        with patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "run_git") as git:
            git.return_value.stdout = "different " + BASE + " " + BASE
            with self.assertRaisesRegex(queue.QueueError, "outside coordinator control"):
                queue._prepare(ROOT_PATH, REPO, 1, admission(1, 20), pr(1, NEW_HEAD))

    def test_failed_recovery_proof_does_not_authorize_updated_head(self) -> None:
        with patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "run_git") as git:
            git.return_value.stdout = f"{NEW_HEAD} different-parent {BASE}"
            with self.assertRaisesRegex(queue.QueueError, "outside coordinator control"):
                queue._prepare(ROOT_PATH, REPO, 1, admission(1, 20), pr(1, NEW_HEAD))

    def _prepare_overlapping(self, conflicts: list[str]):
        from subprocess import CompletedProcess

        def git(args: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if args[0] == "merge-base":
                return CompletedProcess(args, 0 if args[2] == BASE else 1, "", "")
            if args[0] == "diff":
                return CompletedProcess(args, 0, "task.py\n", "")
            if args[0] == "merge-tree":
                return CompletedProcess(args, 1 if conflicts else 0, "tree\n" + "".join(c + "\n" for c in conflicts), "")
            return CompletedProcess(args, 0, "", "")
        heads = iter([NEW_HEAD])
        with patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "_main", return_value=NEW_HEAD), \
             patch.object(queue, "run_git", side_effect=git), \
             patch.object(queue, "_task_paths", return_value={"task.py"}), \
             patch.object(queue, "_raise_if_owned_elsewhere"), \
             patch.object(queue, "_comment"), \
             patch.object(queue.time, "sleep"), \
             patch.object(queue, "_pr", side_effect=lambda *a: pr(1, next(heads, NEW_HEAD))), \
             patch.object(queue, "_gh") as gh:
            try:
                return queue._prepare(ROOT_PATH, REPO, 1, admission(1, 20), pr(1)), gh
            except queue.QueueError as exc:
                return exc, gh

    def test_path_overlap_with_a_clean_merge_does_not_block_branch_update(self) -> None:
        result, gh = self._prepare_overlapping([])
        self.assertEqual(result, (NEW_HEAD, NEW_HEAD))
        self.assertEqual(gh.call_args.args[1:4], ("api", "-X", "PUT"))

    def test_real_merge_conflict_needs_integration_repair_before_branch_update(self) -> None:
        result, gh = self._prepare_overlapping(["task.py"])
        self.assertIsInstance(result, queue.IntegrationRepairNeeded)
        self.assertIn("task.py", str(result))
        gh.assert_not_called()


class TransitionRecordTests(unittest.TestCase):
    def test_transition_publishes_v2_record_and_projects_one_lifecycle_label(self) -> None:
        import json
        from subprocess import CompletedProcess

        posted: list[str] = []
        labels: list[tuple[str, bool]] = []

        def gh(_root: Path, *args: str, data: dict | None = None) -> None:
            posted.append((data or {})["body"])

        observed = {"number": 7, "state": "open", "head": {"sha": HEAD}, "labels": [{"name": "lifecycle:ready"}]}

        def label(_root: Path, _repo: str, _number: int, name: str, *, present: bool) -> None:
            labels.append((name, present))

        with patch.object(queue, "_gh", side_effect=gh), patch.object(queue, "_label", side_effect=label), \
             patch.object(queue, "_pr", return_value=observed), patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            queue._transition(ROOT_PATH, REPO, 7, "blocked-escalation", HEAD, task_identity={"head": HEAD},
                              red_gate={"name": "publication", "identity": HEAD, "evidence": "failed check"})
        self.assertEqual(len(posted), 1)
        self.assertTrue(posted[0].startswith("dev-platform-publication-queue:v2 "))
        record = json.loads(posted[0].split(" ", 1)[1])
        self.assertEqual((record["state"], record["head"], record["red_gate"]["evidence"]), ("blocked-escalation", HEAD, "failed check"))
        self.assertEqual([name for name, present in labels if present], ["lifecycle:blocked-escalation"])
        self.assertEqual(labels, [("lifecycle:ready", False), ("lifecycle:blocked-escalation", True)])

    def _observe(self, comments: list[dict], head: str = HEAD) -> tuple[list[str], dict | None]:
        from subprocess import CompletedProcess

        posted: list[str] = []
        observed = {"number": 7, "state": "open", "head": {"sha": head}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=comments), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            record = queue._transition(ROOT_PATH, REPO, 7, "integrating", HEAD, task_identity={"head": HEAD},
                                       gates={"required-checks": {"result": "passed", "identity": HEAD, "evidence": "ok"}}
                                       if comments else None)
        return posted, record

    def test_transition_carries_forward_and_skips_unchanged_or_moved_head(self) -> None:
        from candidate_lifecycle import build_handoff_record, marker_body

        prior = build_handoff_record(number=7, state="integrating", head=HEAD, task_identity="content-digest",
                                     gates={"review": {"result": "passed", "identity": "content-digest", "evidence": "r1"}},
                                     red_gate=None, not_reverified=["browser"], attempts={"integration": 2},
                                     next_job=None, at="2026-10-05T08:00:00Z")
        posted, record = self._observe([{"id": 1, "author_association": "OWNER", "body": marker_body(prior)}])
        self.assertEqual(len(posted), 1)
        self.assertEqual(set(record["gates"]), {"review", "required-checks"})
        self.assertEqual((record["task_identity"], record["attempts"], record["not_reverified"]),
                         ("content-digest", {"integration": 2}, ["browser"]))
        # The same state with nothing new is not re-published by scheduled retries.
        posted, _ = self._observe_unchanged(prior)
        self.assertEqual(posted, [])
        posted, record = self._observe([], head=NEW_HEAD)
        self.assertEqual((posted, record), ([], None))

    def _observe_unchanged(self, prior: dict) -> tuple[list[str], dict | None]:
        from subprocess import CompletedProcess
        from candidate_lifecycle import marker_body

        posted: list[str] = []
        observed = {"number": 7, "state": "open", "head": {"sha": HEAD}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=[{"id": 1, "author_association": "OWNER", "body": marker_body(prior)}]), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            record = queue._transition(ROOT_PATH, REPO, 7, "integrating", HEAD, task_identity={"head": HEAD})
        return posted, record

    def test_new_admission_records_ready_for_its_exact_head(self) -> None:
        replacement = admission(1, 19, NEW_HEAD)
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1, NEW_HEAD)), \
             patch.object(queue, "_events", side_effect=[[], [replacement]]), \
             patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "_ensure_labels"), patch.object(queue, "_comment"), patch.object(queue, "_label"), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_admission_handoff", return_value={"task_identity": {"head": NEW_HEAD}, "gates": {}}), \
             patch.object(queue, "_transition") as transition:
            queue.admit(ROOT_PATH, 1, NEW_HEAD)
        transition.assert_called_once()
        args, kwargs = transition.call_args
        self.assertEqual(args, (ROOT_PATH, REPO, 1, "ready", NEW_HEAD))
        self.assertIn("task_identity", kwargs)


class WorkerLifecycleTests(unittest.TestCase):
    def _worker(self, body: str) -> tuple[dict, object]:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", return_value=[{"id": 30, "author_association": "OWNER", "body": body}]), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), \
             patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare") as prepare:
            return queue.worker(ROOT_PATH), prepare

    def test_worker_does_not_integrate_a_candidate_owned_by_a_review_job(self) -> None:
        from candidate_lifecycle import build_handoff_record, marker_body

        record = build_handoff_record(number=1, state="reviewing", head=HEAD, task_identity="digest", gates={},
                                      red_gate=None, not_reverified=[], attempts={}, next_job=None,
                                      at="2026-10-05T08:00:00Z")
        result, prepare = self._worker(marker_body(record))
        self.assertEqual(result["state"], "waiting")
        self.assertIn("reviewing", result["reason"])
        prepare.assert_not_called()

    def test_worker_does_not_integrate_a_blocked_retryable_review(self) -> None:
        from candidate_lifecycle import build_handoff_record, marker_body

        record = build_handoff_record(number=1, state="blocked-retryable", head=HEAD, task_identity="digest", gates={},
                                      red_gate={"name": "review", "identity": "digest", "evidence": {}},
                                      not_reverified=[], attempts={"review": 1},
                                      next_job={"kind": "review", "head": HEAD, "task_identity": "digest", "attempt": 1},
                                      at="2026-10-05T08:00:00Z")
        result, prepare = self._worker(marker_body(record))
        self.assertEqual(result["state"], "waiting")
        self.assertIn("blocked-retryable", result["reason"])
        prepare.assert_not_called()

    def test_worker_blocks_on_a_malformed_lifecycle_record(self) -> None:
        result, prepare = self._worker("dev-platform-publication-queue:v2 {broken")
        self.assertEqual(result["state"], "blocked")
        self.assertIn("malformed marker", result["reason"])
        prepare.assert_not_called()


class WorkerRecoveryAndAttemptTests(unittest.TestCase):
    def test_record_for_an_older_head_does_not_block_branch_update_recovery(self) -> None:
        from candidate_lifecycle import build_handoff_record, marker_body

        old = build_handoff_record(number=1, state="ready", head=HEAD, task_identity="digest", gates={},
                                   red_gate=None, not_reverified=[], attempts={}, next_job=None,
                                   at="2026-10-05T08:00:00Z")
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1, NEW_HEAD)), \
             patch.object(queue, "_comments", return_value=[{"id": 30, "author_association": "OWNER", "body": marker_body(old)}]), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", side_effect=queue.QueueError("recovery reached")) as prepare:
            result = queue.worker(ROOT_PATH)
        prepare.assert_called_once()
        self.assertIn("recovery reached", result["reason"])

    def test_integration_attempt_counts_state_entries_not_scheduled_retries(self) -> None:
        from subprocess import CompletedProcess
        from candidate_lifecycle import build_handoff_record, marker_body

        ready = build_handoff_record(number=7, state="ready", head=HEAD, task_identity="digest", gates={},
                                     red_gate=None, not_reverified=[], attempts={"integration": 1}, next_job=None,
                                     at="2026-10-05T08:00:00Z")
        posted: list[str] = []
        labels: list[tuple[str, bool]] = []
        comments = [{"id": 1, "author_association": "OWNER", "body": marker_body(ready)}]
        observed = {"number": 7, "state": "open", "head": {"sha": HEAD}, "labels": [{"name": "lifecycle:ready"}]}

        def gh(_root: Path, *args: str, data: dict | None = None) -> None:
            posted.append(data["body"])
            comments.append({"id": len(comments) + 1, "author_association": "OWNER", "body": data["body"]})

        with patch.object(queue, "_gh", side_effect=gh), \
             patch.object(queue, "_label", side_effect=lambda *a, present: labels.append((a[3], present))), \
             patch.object(queue, "_pr", return_value=observed), patch.object(queue, "_comments", side_effect=lambda *a: list(comments)), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            first = queue._transition(ROOT_PATH, REPO, 7, "integrating", HEAD, task_identity="digest", attempt="integration")
            labels.clear()
            second = queue._transition(ROOT_PATH, REPO, 7, "integrating", HEAD, task_identity="digest", attempt="integration")
        self.assertEqual(first["attempts"], {"integration": 2})
        self.assertEqual(second["attempts"], {"integration": 2})
        self.assertEqual(len(posted), 1)
        # The stale observed label set is repaired even when no record is published.
        self.assertEqual(labels, [("lifecycle:ready", False), ("lifecycle:integrating", True)])


class WorkerSkipAndMergeTests(unittest.TestCase):
    def _record(self, number: int, state: str, head: str = HEAD) -> dict:
        from candidate_lifecycle import build_handoff_record, marker_body

        record = build_handoff_record(number=number, state=state, head=head, task_identity="digest", gates={},
                                      red_gate=None, not_reverified=[], attempts={}, next_job=None,
                                      at="2026-10-05T08:00:00Z")
        return {"id": 40 + number, "author_association": "OWNER", "body": marker_body(record)}

    def test_escalated_or_repairing_candidates_are_skipped_not_integrated(self) -> None:
        comments = {1: [self._record(1, "blocked-escalation")], 2: [self._record(2, "integration-repair-pending", NEW_HEAD)],
                    3: []}
        prs = {1: pr(1), 2: pr(2, NEW_HEAD), 3: pr(3)}
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17)), (18, 2, admission(2, 18, NEW_HEAD)),
                                                          (19, 3, admission(3, 19))]), \
             patch.object(queue, "_pr", side_effect=lambda _r, _repo, number: prs[number]), \
             patch.object(queue, "_comments", side_effect=lambda _r, _repo, number: comments[number]), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", side_effect=queue.QueueError("stop")) as prepare, \
             patch.object(queue, "_block", return_value={"state": "blocked"}):
            queue.worker(ROOT_PATH)
        self.assertEqual(prepare.call_args.args[2], 3)

    def test_only_skipped_candidates_leave_the_queue_waiting(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", return_value=[self._record(1, "blocked-escalation")]), \
             patch.object(queue, "_prepare") as prepare:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        self.assertIn("blocked-escalation", result["reason"])
        prepare.assert_not_called()

    def test_lost_merged_record_does_not_block_a_merged_candidate(self) -> None:
        from subprocess import CompletedProcess

        merged = {**pr(1), "merged": True}
        observations = iter([pr(1), merged])
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", side_effect=lambda *a: next(observations, merged)), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("passed", "ok", ())), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")), \
             patch.object(queue, "_transition", side_effect=[None, queue.QueueError("comment POST failed")]), \
             patch.object(queue, "_block") as block:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "merged")
        block.assert_not_called()


class LineageAndOwnershipTests(unittest.TestCase):
    @staticmethod
    def _comment(number: int, state: str, head: str, **fields: object) -> dict:
        from candidate_lifecycle import build_handoff_record, marker_body

        values = {"task_identity": {"task_content": "d" * 64}, "gates": {}, "attempts": {}, **fields}
        record = build_handoff_record(number=number, state=state, head=head, red_gate=None, not_reverified=[],
                                      next_job=fields.get("next_job"), at="2026-10-05T08:00:00Z",
                                      **{k: values[k] for k in ("task_identity", "gates", "attempts")})
        return {"id": 50, "author_association": "OWNER", "body": marker_body(record)}

    def _run(self, comments: list[dict], head: str, **kwargs: object) -> tuple[list[str], object]:
        from subprocess import CompletedProcess

        posted: list[str] = []
        observed = {"number": 7, "state": "open", "head": {"sha": head}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=comments), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            record = queue._transition(ROOT_PATH, REPO, 7, "integrating", head, task_identity={"branch": "agent/7", "head": head}, **kwargs)
        return posted, record

    def test_coordinator_head_update_keeps_task_identity_and_attempts_but_not_gates(self) -> None:
        old = self._comment(7, "integrating", HEAD, attempts={"integration": 2},
                            gates={"required-checks": {"result": "passed", "identity": HEAD, "evidence": "ok"}})
        _, record = self._run([old], NEW_HEAD, attempt="integration")
        self.assertEqual(record["task_identity"], {"task_content": "d" * 64})
        self.assertEqual(record["attempts"], {"integration": 3})
        self.assertEqual(record["gates"], {})

    def test_head_update_keeps_items_not_reverified(self) -> None:
        from candidate_lifecycle import build_handoff_record, marker_body

        old = build_handoff_record(number=7, state="integrating", head=HEAD, task_identity="digest", gates={},
                                   red_gate=None, not_reverified=["browser"], attempts={}, next_job=None,
                                   at="2026-10-05T08:00:00Z")
        _, record = self._run([{"id": 50, "author_association": "OWNER", "body": marker_body(old)}], NEW_HEAD)
        self.assertEqual(record["not_reverified"], ["browser"])

    def test_claim_on_the_pre_update_head_still_refuses_integration(self) -> None:
        owned = self._comment(7, "reviewing", HEAD)
        with self.assertRaises(queue.LifecycleOwnershipChanged):
            self._run([owned], NEW_HEAD, attempt="integration", refuse_from=queue.NOT_INTEGRABLE, cross_head_claims=True)

    def test_old_head_block_never_vetoes_a_freshly_admitted_head(self) -> None:
        blocked = self._comment(7, "blocked-escalation", HEAD)
        posted, record = self._run([blocked], NEW_HEAD, attempt="integration", refuse_from=queue.NOT_INTEGRABLE,
                                   cross_head_claims=True)
        self.assertEqual((len(posted), record["state"]), (1, "integrating"))
        from subprocess import CompletedProcess

        posted = []
        observed = {"number": 7, "state": "open", "head": {"sha": NEW_HEAD}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=[blocked]), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            ready = queue._transition(ROOT_PATH, REPO, 7, "ready", NEW_HEAD, task_identity={"task_content": "f" * 64},
                                      inherit_identity=False, refuse_from=queue.STATES)
        self.assertEqual((len(posted), ready["state"]), (1, "ready"))

    def test_block_after_integrating_publishes_its_own_record(self) -> None:
        import json

        integrating = self._comment(7, "integrating", HEAD)
        v1_block = {"id": 51, "author_association": "OWNER",
                    "body": queue.PREFIX + json.dumps({"version": 1, "number": 7, "kind": "block", "reason": "check failed"})}
        posted, record = self._run_state([integrating, v1_block], HEAD, "blocked-escalation",
                                         red_gate={"name": "publication", "identity": HEAD, "evidence": "check failed"})
        self.assertEqual(len(posted), 1)
        self.assertEqual(record["state"], "blocked-escalation")

    def _run_state(self, comments: list[dict], head: str, state: str, **kwargs: object) -> tuple[list[str], object]:
        from subprocess import CompletedProcess

        posted: list[str] = []
        observed = {"number": 7, "state": "open", "head": {"sha": head}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=comments), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            record = queue._transition(ROOT_PATH, REPO, 7, state, head, task_identity={"head": head},
                                       inherit_identity=False, **kwargs)
        return posted, record

    def test_integration_refuses_a_candidate_newly_owned_by_review(self) -> None:
        owned = self._comment(7, "reviewing", HEAD, next_job={"kind": "review", "claim": "worker-1"})
        with self.assertRaises(queue.LifecycleOwnershipChanged):
            self._run([owned], HEAD, attempt="integration", refuse_from=queue.NOT_INTEGRABLE)

    def _admit(self, comments: list[dict]) -> object:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_events", return_value=[admission(1, 17)]), \
             patch.object(queue, "_comments", return_value=comments), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), \
             patch.object(queue, "_admission_handoff", return_value={"task_identity": {"head": HEAD}, "gates": {}}), \
             patch.object(queue, "_transition") as transition:
            queue.admit(ROOT_PATH, 1, HEAD)
        return transition

    def test_admission_retry_recovers_a_missing_ready_record(self) -> None:
        transition = self._admit([])
        self.assertEqual(transition.call_args.args[3], "ready")

    def test_readmission_binds_the_freshly_validated_identity(self) -> None:
        old = self._comment(7, "blocked-escalation", HEAD)
        fresh = {"task_content": "e" * 64}
        from subprocess import CompletedProcess

        posted: list[str] = []
        observed = {"number": 7, "state": "open", "head": {"sha": NEW_HEAD}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=[old]), \
             patch.object(queue.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            record = queue._transition(ROOT_PATH, REPO, 7, "ready", NEW_HEAD, task_identity=fresh, inherit_identity=False,
                                       gates={"local-validation": {"result": "passed", "identity": fresh, "evidence": "x"}})
        self.assertEqual(record["task_identity"], fresh)

    def test_admission_retry_never_rewinds_later_lifecycle_state(self) -> None:
        transition = self._admit([self._comment(1, "integrating", HEAD)])
        transition.assert_not_called()


class IntegrationJobAndClaimTests(unittest.TestCase):
    def test_integrating_record_names_the_integration_job(self) -> None:
        posted, record = LineageAndOwnershipTests._run(
            LineageAndOwnershipTests(), [], HEAD, attempt="integration",
            next_job={"kind": "integration", "claim": "publication-queue workflow", "head": HEAD})
        self.assertEqual(record["next_job"]["claim"], "publication-queue workflow")

    def test_changed_claim_on_the_same_state_is_published(self) -> None:
        integrating = LineageAndOwnershipTests._comment(7, "integrating", HEAD)
        claim = {"kind": "integration", "claim": "publication-queue workflow", "head": HEAD}
        posted, record = LineageAndOwnershipTests._run(LineageAndOwnershipTests(), [integrating], HEAD, next_job=claim)
        self.assertEqual(len(posted), 1)
        self.assertEqual(record["next_job"], claim)

    def test_older_head_claim_is_skipped_before_preparation(self) -> None:
        reviewing = LineageAndOwnershipTests._comment(1, "reviewing", HEAD)
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1, NEW_HEAD)), \
             patch.object(queue, "_comments", return_value=[reviewing]), \
             patch.object(queue, "_prepare") as prepare, patch.object(queue, "_block") as block:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        prepare.assert_not_called()
        block.assert_not_called()


class Round12Tests(unittest.TestCase):
    def test_admission_binds_the_archived_automated_checks_as_a_gate(self) -> None:
        import hashlib
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "openspec" / "changes" / "archive" / "2026-10-05-sample-change"
            archive.mkdir(parents=True)
            evidence = {"outcome": "success", "managed_checkout": {"task_content": {"digest": "a" * 64}, "head": HEAD}}
            (archive / "automated-checks.json").write_text(json.dumps(evidence), encoding="utf-8")
            raw = (archive / "automated-checks.json").read_bytes()
            with patch("managed_task.read_task_state", return_value={"change": "sample-change"}):
                gate = queue._archived_verification_gate(root)
            self.assertEqual(gate["archived-verification"]["identity"], {"task_content": "a" * 64, "head": HEAD})
            self.assertEqual(gate["archived-verification"]["evidence"]["sha256"], hashlib.sha256(raw).hexdigest())
            evidence["outcome"] = "failure"
            (archive / "automated-checks.json").write_text(json.dumps(evidence), encoding="utf-8")
            with patch("managed_task.read_task_state", return_value={"change": "sample-change"}):
                self.assertEqual(queue._archived_verification_gate(root), {})

    def test_queue_events_ignore_untrusted_markers(self) -> None:
        import json

        owner = {"id": 1, "author_association": "OWNER", "body": queue.PREFIX + json.dumps(
            {"version": 1, "number": 1, "kind": "admit", "head": HEAD, "base": BASE, "branch": "agent/1"})}
        forged = {"id": 2, "author_association": "NONE", "body": queue.PREFIX + json.dumps(
            {"version": 1, "number": 1, "kind": "block", "reason": "forged"})}
        with patch.object(queue, "_comments", return_value=[owner, forged]), \
             patch.object(queue, "trusted_apps", return_value=frozenset()):
            events = queue._events(ROOT_PATH, REPO, 1)
        self.assertEqual([event["kind"] for event in events], ["admit"])
        self.assertIsNotNone(queue._admission(events, 1))

    def test_check_failure_does_not_block_a_candidate_claimed_meanwhile(self) -> None:
        reviewing = LineageAndOwnershipTests._comment(1, "reviewing", HEAD)
        observations = iter([[], [reviewing]])
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", side_effect=lambda *a: next(observations, [reviewing])), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("failed", "validate", ())), \
             patch.object(queue, "_block") as block:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        block.assert_not_called()


class Round13Tests(unittest.TestCase):
    def test_unknown_check_error_does_not_block_a_candidate_claimed_meanwhile(self) -> None:
        reviewing = LineageAndOwnershipTests._comment(1, "reviewing", HEAD)
        observations = iter([[], [reviewing]])
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", side_effect=lambda *a: next(observations, [reviewing])), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("unknown", "api down", (), "malformed")), \
             patch.object(queue, "_block") as block:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        block.assert_not_called()


class Round14Tests(unittest.TestCase):
    def test_already_active_candidate_is_resumed_before_any_other(self) -> None:
        prs = {1: pr(1), 2: pr(2, NEW_HEAD, labels=(queue.QUEUE, queue.ACTIVE))}
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17)), (18, 2, admission(2, 18, NEW_HEAD))]), \
             patch.object(queue, "_pr", side_effect=lambda _r, _repo, number: prs[number]), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", side_effect=queue.QueueError("stop")) as prepare, \
             patch.object(queue, "_block", return_value={"state": "blocked"}):
            queue.worker(ROOT_PATH)
        self.assertEqual(prepare.call_args_list[0].args[2], 2)

    def test_prepare_rechecks_ownership_before_updating_the_branch(self) -> None:
        calls: list[tuple] = []
        with patch.object(queue, "_events", return_value=[]), \
             patch.object(queue, "_main", return_value=NEW_HEAD), \
             patch.object(queue, "run_git", side_effect=lambda args, **kw: __import__("subprocess").CompletedProcess(
                 args, 1 if args[:2] == ["merge-base", "--is-ancestor"] and args[2] == NEW_HEAD else 0, "", "")), \
             patch.object(queue, "_task_paths", return_value={"x.py"}), \
             patch.object(queue, "_raise_if_owned_elsewhere", side_effect=queue.LifecycleOwnershipChanged("now reviewing")), \
             patch.object(queue, "_gh", side_effect=lambda *a, **k: calls.append(a)):
            with self.assertRaises(queue.LifecycleOwnershipChanged):
                queue._prepare(ROOT_PATH, REPO, 1, {**admission(1, 17), "comment_id": 17}, pr(1))
        self.assertFalse(any("update-branch" in str(call) for call in calls))


class UnobservableOwnershipTests(unittest.TestCase):
    def test_error_with_unobservable_ownership_waits_instead_of_blocking(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_label"), \
             patch.object(queue, "_prepare", side_effect=queue.QueueError("update failed")), \
             patch.object(queue, "_raise_if_owned_elsewhere", side_effect=queue.QueueError("HTTP 502")), \
             patch.object(queue, "_block") as block:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        self.assertIn("unobservable", result["reason"])
        block.assert_not_called()


class RetryJobOwnershipTests(unittest.TestCase):
    def test_blocked_retryable_review_and_repair_states_are_job_owned(self) -> None:
        unavailable = {"cause": "provider-unavailable"}
        owned = {
            "review next_job": ({"state": "blocked-retryable", "next_job": {"kind": "review"}}, "review"),
            "review red gate": ({"state": "blocked-retryable", "red_gate": {"name": "review"}}, "review"),
            "repair next_job": ({"state": "blocked-retryable", "next_job": {"kind": "repair"}}, "repair"),
            "repair streak exhausted": (
                {"state": "blocked-retryable", "next_job": None,
                 "gates": {"repair": {"status": "failed", "evidence": unavailable}}},
                "repair",
            ),
        }
        for label, (candidate, kind) in owned.items():
            with self.subTest(label):
                self.assertEqual(queue.retry_job_kind(candidate), kind)
                self.assertTrue(queue.review_owned(candidate))
        not_owned = {
            "required-checks red gate": {"state": "blocked-retryable", "next_job": None,
                                         "red_gate": {"name": "required-checks"}, "gates": {}},
            "repair failed without provider cause": {"state": "blocked-retryable",
                                                     "gates": {"repair": {"status": "failed", "evidence": {}}}},
            "review next_job but other state": {"state": "blocked-escalation", "next_job": {"kind": "review"}},
            "review red gate but other state": {"state": "queued", "red_gate": {"name": "review"}},
            "repair unavailable but other state": {"state": "blocked-escalation",
                                                   "gates": {"repair": {"status": "failed", "evidence": unavailable}}},
        }
        for label, candidate in not_owned.items():
            with self.subTest(label):
                self.assertIsNone(queue.retry_job_kind(candidate))
                self.assertFalse(queue.review_owned(candidate))


class MalformedDuringIntegrationTests(unittest.TestCase):
    def test_malformed_record_arriving_during_check_wait_stops_the_merge(self) -> None:
        broken = {"id": 60, "author_association": "OWNER", "body": "dev-platform-publication-queue:v2 {broken"}
        observations = iter([[], [broken]])
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", side_effect=lambda *a: next(observations, [broken])), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("passed", "ok", ())), \
             patch.object(queue.subprocess, "run") as run:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        self.assertFalse(any(call.args and call.args[0][:3] == ["gh", "pr", "merge"] for call in run.call_args_list))


class BlockRobustnessTests(unittest.TestCase):
    def test_block_dequeues_even_when_the_handoff_record_fails(self) -> None:
        labels: list[tuple[str, bool]] = []
        with patch.object(queue, "_comment"), \
             patch.object(queue, "_label", side_effect=lambda *a, present: labels.append((a[3], present))), \
             patch.object(queue, "_transition", side_effect=queue.QueueError("comment page full")) as transition:
            result = queue._block(ROOT_PATH, REPO, 7, "head changed outside coordinator control", head=NEW_HEAD)
        self.assertEqual(result["state"], "blocked")
        self.assertIn((queue.QUEUE, False), labels)
        self.assertIs(transition.call_args.kwargs["inherit_identity"], False)

    def test_admission_retry_refuses_a_concurrently_recorded_head(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_events", return_value=[admission(1, 17)]), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), \
             patch.object(queue, "_admission_handoff", return_value={"task_identity": {"head": HEAD}, "gates": {}}), \
             patch.object(queue, "_transition", side_effect=queue.LifecycleOwnershipChanged("now reviewing")) as transition:
            result = queue.admit(ROOT_PATH, 1, HEAD)
        self.assertEqual(result["state"], "queued")
        self.assertEqual(transition.call_args.kwargs["refuse_from"], queue.STATES)


class MergeOwnershipTests(unittest.TestCase):
    def test_claim_during_check_wait_stops_the_merge(self) -> None:
        reviewing = LineageAndOwnershipTests._comment(1, "reviewing", HEAD)
        observations = iter([[], [reviewing]])
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(17, 1, admission(1, 17))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", side_effect=lambda *a: next(observations, [reviewing])), \
             patch.object(queue, "_label"), patch.object(queue, "_comment"), patch.object(queue, "_transition"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("passed", "ok", ())), \
             patch.object(queue.subprocess, "run") as run:
            result = queue.worker(ROOT_PATH)
        self.assertEqual(result["state"], "waiting")
        self.assertIn("reviewing", result["reason"])
        self.assertFalse(any(call.args and call.args[0][:3] == ["gh", "pr", "merge"] for call in run.call_args_list))


class WorkflowTrustBoundaryTests(unittest.TestCase):
    """The coordinator must run default-branch code with a least-privilege App token."""

    def setUp(self) -> None:
        path = ROOT / ".github" / "workflows" / "publication-queue.yml"
        self.workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        # PyYAML parses the bare `on:` key as boolean True.
        self.triggers = self.workflow.get("on", self.workflow.get(True))
        self.steps = [step for job in self.workflow["jobs"].values() for step in job.get("steps", [])]

    def test_label_trigger_runs_default_branch_code(self) -> None:
        self.assertNotIn("pull_request", self.triggers)
        self.assertEqual(self.triggers["pull_request_target"], {"types": ["labeled"]})
        job = self.workflow["jobs"]["publish-next"]
        self.assertIn("pull_request_target", job["if"])
        self.assertIn("publication:queued", job["if"])

    def test_no_step_checks_out_pull_request_content(self) -> None:
        for step in self.steps:
            if not str(step.get("uses", "")).startswith("actions/checkout@"):
                continue
            with self.subTest(step=step):
                options = step.get("with") or {}
                self.assertNotIn("repository", options)
                ref = str(options.get("ref", ""))
                self.assertNotIn("pull_request", ref)
                self.assertNotIn("refs/pull", ref)
                self.assertNotIn("head", ref)

    def test_app_token_is_scoped_to_repository_and_queue_permissions(self) -> None:
        token_steps = [step for step in self.steps
                       if str(step.get("uses", "")).startswith("actions/create-github-app-token@")]
        self.assertEqual(len(token_steps), 1)
        options = token_steps[0]["with"]
        self.assertEqual(options.get("owner"), "${{ github.repository_owner }}")
        # schedule payloads may lack github.event.repository, which would leave
        # `repositories` empty and widen the token to the whole installation.
        self.assertEqual(options.get("repositories"), "${{ steps.repo.outputs.name }}")
        repo_steps = [step for step in self.steps if step.get("id") == "repo"]
        self.assertEqual(len(repo_steps), 1)
        self.assertIn("GITHUB_REPOSITORY", repo_steps[0]["run"])
        permissions = {key: value for key, value in options.items() if key.startswith("permission-")}
        self.assertEqual(permissions, {"permission-contents": "write", "permission-pull-requests": "write"})
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})


class CommentHistoryTests(unittest.TestCase):
    @staticmethod
    def rows(count: int, start: int = 1) -> list[dict]:
        return [{"id": start + index, "body": f"c{index}"} for index in range(count)]

    @staticmethod
    def pages(rows: list[dict]) -> list[list[dict]]:
        return [rows[i:i + 100] for i in range(0, len(rows), 100)] or [[]]

    def read(self, observed):
        with patch.object(queue, "_gh", return_value=observed) as gh:
            result = queue._comments(ROOT_PATH, REPO, 7)
        self.assertEqual(gh.call_args.args[1:4], ("api", "--paginate", "--slurp"))
        return result

    def test_histories_of_every_boundary_size_are_complete_and_ordered(self) -> None:
        for count in (0, 99, 100, 101, 200):
            with self.subTest(count=count):
                rows = self.rows(count)
                self.assertEqual(self.read(self.pages(rows)), rows)

    def test_a_later_page_marker_participates_in_replay(self) -> None:
        marker = {"id": 1000, "author_association": "OWNER", "body": queue.PREFIX + json.dumps(
            {"version": 1, "number": 7, "kind": "admit", "head": HEAD, "base": BASE, "branch": "agent/7"})}
        observed = self.pages([*self.rows(100), marker])
        self.assertEqual(len(observed), 2)
        with patch.object(queue, "_gh", return_value=observed), \
             patch.object(queue, "trusted_apps", return_value=frozenset()):
            events = queue._events(ROOT_PATH, REPO, 7)
        self.assertEqual([event["kind"] for event in events], ["admit"])

    def test_every_invalid_observation_raises_the_named_error_without_a_prefix(self) -> None:
        good = self.rows(2)
        cases = {
            "empty body": None,
            "no pages": [],
            "outer value is not an array": {"id": 1},
            "page is not an array": [good, {"id": 3}],
            "non-object row": [[*good, "text"]],
            "row without an id": [[*good, {"body": "x"}]],
            "boolean id": [[*good, {"id": True}]],
            "string id": [[*good, {"id": "9"}]],
            "duplicate id across pages": [good, [{"id": 2}]],
            "regressing id across pages": [good, [{"id": 1}]],
        }
        for name, observed in cases.items():
            with self.subTest(name), patch.object(queue, "_gh", return_value=observed):
                with self.assertRaisesRegex(queue.QueueError, "comment-history acquisition failed for #7"):
                    queue._comments(ROOT_PATH, REPO, 7)

    def test_transport_failure_and_invalid_json_are_named(self) -> None:
        with patch.object(queue, "_gh", side_effect=queue.QueueError("page 2 unavailable")):
            with self.assertRaisesRegex(queue.QueueError, "comment-history acquisition failed for #7: page 2 unavailable"):
                queue._comments(ROOT_PATH, REPO, 7)
        from subprocess import CompletedProcess
        with patch("_platform_common.run_github_with_retry", return_value=CompletedProcess([], 0, "[[{", "")):
            with self.assertRaisesRegex(queue.QueueError, "comment-history acquisition failed for #7"):
                queue._comments(ROOT_PATH, REPO, 7)


class TrustConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(queue.COORDINATOR_APP_ENV, None)
        os.environ.pop("DEV_PLATFORM_OPERATOR_CONFIG", None)

    def config(self, text: str) -> None:
        (self.root / ".dev-platform.toml").write_text(text, encoding="utf-8")

    def operator(self, text: str, *, write: bool = True) -> None:
        path = self.root / "operator.toml"
        if write:
            path.write_text(text, encoding="utf-8")
        self.config(f'[operator]\nenabled = true\nconfig_path = "{path}"\n')

    def test_valid_sources_are_unioned_with_the_environment_name(self) -> None:
        import os

        os.environ[queue.COORDINATOR_APP_ENV] = "env-app"
        self.operator('[publication]\ncoordinator_app = "operator-app"\n')
        self.assertEqual(queue.trusted_apps(self.root), {"env-app", "operator-app"})
        self.config('[publication]\ncoordinator_app = "project-app"\n')
        self.assertEqual(queue.trusted_apps(self.root), {"env-app", "project-app"})

    def test_documented_absence_contributes_nothing_without_error(self) -> None:
        self.assertEqual(queue.trusted_apps(self.root), frozenset())  # no project config
        self.config('[operator]\nenabled = false\n')
        self.assertEqual(queue.trusted_apps(self.root), frozenset())  # operator disabled, no [publication]
        self.operator("")  # enabled operator config without a publication table
        self.assertEqual(queue.trusted_apps(self.root), frozenset())

    def test_invalid_configured_sources_raise_naming_the_source(self) -> None:
        cases = {
            "invalid TOML": (lambda: self.config("this is = = not toml"), r"\.dev-platform\.toml is unreadable"),
            "non-table publication": (lambda: self.config('publication = "x"\n'), r"\.dev-platform\.toml is unreadable"),
            "non-string app": (lambda: self.config("[publication]\ncoordinator_app = 5\n"), r"\.dev-platform\.toml is unreadable"),
            "missing operator config": (lambda: self.operator("", write=False), r"operator config is unreadable or invalid: operator configuration was requested"),
            "invalid operator TOML": (lambda: self.operator("= broken"), r"operator config is unreadable or invalid: "),
            "non-string operator app": (lambda: self.operator("[publication]\ncoordinator_app = [1]\n"), r"operator config is unreadable or invalid: "),
        }
        for name, (setup, source) in cases.items():
            setup()
            with self.subTest(name), self.assertRaisesRegex(queue.QueueError, f"trust source {source}"):
                queue.trusted_apps(self.root)
            (self.root / "operator.toml").unlink(missing_ok=True)

    def test_operator_override_cannot_mask_invalid_project_trust_source(self) -> None:
        for text in ('publication = "invalid"\n', "[publication]\ncoordinator_app = 123\n"):
            self.config(text + '[operator]\nenabled = true\nconfig_path = "operator.toml"\n')
            (self.root / "operator.toml").write_text('[publication]\ncoordinator_app = "operator-app"\n', encoding="utf-8")
            with self.subTest(text), self.assertRaisesRegex(queue.QueueError, r"trust source \.dev-platform\.toml"):
                queue.trusted_apps(self.root)

    def test_admission_and_worker_callers_stop_instead_of_narrowing_trust(self) -> None:
        import lifecycle_workers

        self.config("this is = = not toml")
        with self.assertRaisesRegex(queue.QueueError, "trust source .dev-platform.toml"):
            lifecycle_workers._coordinator_trust(self.root)
        with patch.object(queue, "_repo", return_value=REPO), patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", return_value=[]):
            with self.assertRaisesRegex(queue.QueueError, "trust source .dev-platform.toml"):
                queue.admit(self.root, 1, HEAD, handoff={"task_identity": {"head": HEAD}, "gates": {}})


class ManagedProvenanceTests(unittest.TestCase):
    """Real git repositories: a managed task, a quick task, and failure modes."""

    def setUp(self) -> None:
        import subprocess
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("switch", "-c", "agent/task")
        self.subprocess = subprocess

    def git(self, *args: str) -> str:
        import subprocess

        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True).stdout.strip()

    def commit(self, relative: str, text: str = "x\n") -> str:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", relative)
        self.git("commit", "-m", f"edit {relative}")
        return self.git("rev-parse", "HEAD")

    def state(self, text: str | None = None) -> None:
        (self.root / ".managed-task-state.json").write_text(
            text if text is not None else json.dumps({"source_issue": "owner/backlog#1", "change": "sample"}), encoding="utf-8")

    def managed_head(self) -> str:
        return self.commit("openspec/changes/sample/proposal.md")

    def test_genuine_quick_task_keeps_branch_head_identity(self) -> None:
        head = self.commit("feature.txt")
        self.assertEqual(queue._admission_handoff(self.root, "agent/task", head),
                         {"task_identity": {"branch": "agent/task", "head": head}, "gates": {}})

    def test_managed_task_with_valid_proof_binds_the_task_content_digest(self) -> None:
        from task_content_identity import content_identity

        head = self.managed_head()
        self.state()
        handoff = queue._admission_handoff(self.root, "agent/task", head)
        self.assertEqual(handoff["task_identity"], {"task_content": content_identity(self.root, "sample")["digest"]})
        self.assertEqual(handoff["gates"], {})

    def test_missing_managed_package_rejects_even_computable_digest(self) -> None:
        head = self.commit("feature.txt")
        self.state()
        from task_content_identity import content_identity

        self.assertTrue(content_identity(self.root, "sample")["digest"])
        with self.assertRaisesRegex(queue.QueueError, "change sample has no unique active or archived package"):
            queue._admission_handoff(self.root, "agent/task", head)

    def test_archived_managed_package_retains_valid_provenance(self) -> None:
        head = self.commit("openspec/changes/archive/2026-10-05-sample/proposal.md")
        self.state()
        self.assertIn("task_content", queue._admission_handoff(self.root, "agent/task", head)["task_identity"])

    def test_managed_task_binds_readable_successful_archived_evidence_only(self) -> None:
        import hashlib

        head = self.managed_head()
        self.state()
        archive = self.root / "openspec/changes/archive/2026-10-05-sample"
        archive.mkdir(parents=True)
        evidence = archive / "automated-checks.json"
        payload = {"outcome": "success", "managed_checkout": {"task_content": {"digest": "a" * 64}, "head": head}}
        evidence.write_text(json.dumps(payload), encoding="utf-8")
        gate = queue._archived_verification_gate(self.root)["archived-verification"]
        self.assertEqual(gate["identity"], {"task_content": "a" * 64, "head": head})
        self.assertEqual(gate["evidence"]["sha256"], hashlib.sha256(evidence.read_bytes()).hexdigest())
        evidence.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(queue.QueueError, "archived verification evidence .* unreadable or malformed"):
            queue._archived_verification_gate(self.root)
        evidence.write_bytes(b"\xff")
        with self.assertRaisesRegex(queue.QueueError, "archived verification evidence .* unreadable or malformed"):
            queue._archived_verification_gate(self.root)
        evidence.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(queue.QueueError, "not a JSON object"):
            queue._archived_verification_gate(self.root)
        evidence.unlink()
        self.assertEqual(queue._archived_verification_gate(self.root), {})

    def test_structurally_malformed_archived_evidence_stops_admission(self) -> None:
        head = self.managed_head()
        self.state()
        archive = self.root / "openspec/changes/archive/2026-10-05-sample"
        archive.mkdir(parents=True)
        evidence = archive / "automated-checks.json"
        valid_checkout = {"task_content": {"digest": "a" * 64}, "head": head}
        cases = [
            {"outcome": "success"},
            {"outcome": "success", "managed_checkout": []},
            {"outcome": "success", "managed_checkout": {"head": head}},
            {"outcome": "success", "managed_checkout": {"task_content": {"digest": 123}}},
            {"outcome": "success", "managed_checkout": {**valid_checkout, "head": None}},
            {"outcome": "success", "managed_checkout": {**valid_checkout, "head": "invalid"}},
            {"outcome": "success", "managed_checkout": {**valid_checkout, "task_content": {"digest": "invalid"}}},
            {"outcome": "unknown", "managed_checkout": valid_checkout},
            {"managed_checkout": valid_checkout},
            {"outcome": "failure"},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                evidence.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(queue.QueueError, "archived verification evidence .* malformed"):
                    queue._admission_handoff(self.root, "agent/task", head)
        evidence.write_text(json.dumps({"outcome": "failure", "managed_checkout": valid_checkout}), encoding="utf-8")
        self.assertEqual(queue._archived_verification_gate(self.root), {})

    def test_managed_failures_raise_and_never_downgrade(self) -> None:
        from subprocess import CompletedProcess

        head = self.managed_head()
        message = "managed candidate agent/task lacks valid exact task-content provenance"
        # Head touches an OpenSpec change but the checkout has no managed state.
        with self.assertRaisesRegex(queue.QueueError, message):
            queue._admission_handoff(self.root, "agent/task", head)
        # Unreadable or invalid managed state.
        for text in ("{broken", json.dumps({"change": "sample"}), "[]"):
            self.state(text)
            with self.subTest(state=text), self.assertRaisesRegex(queue.QueueError, "managed task state is unreadable"):
                queue._admission_handoff(self.root, "agent/task", head)
        self.state()
        # Checkout at another head.
        self.commit("later.txt")
        with self.assertRaisesRegex(queue.QueueError, message + ": the checkout is at"):
            queue._admission_handoff(self.root, "agent/task", head)
        later = self.git("rev-parse", "HEAD")
        # Missing proof and empty digest.
        with patch("task_content_identity.content_identity", return_value=None), \
             self.assertRaisesRegex(queue.QueueError, message + ": no task-content proof"):
            queue._admission_handoff(self.root, "agent/task", later)
        with patch("task_content_identity.content_identity", return_value={"digest": ""}), \
             self.assertRaisesRegex(queue.QueueError, message):
            queue._admission_handoff(self.root, "agent/task", later)
        # A git failure is raised, not turned into a quick-task identity.
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        (self.root / ".managed-task-state.json").unlink()
        with self.assertRaisesRegex(queue.QueueError, "cannot determine the merge base"):
            queue._admission_handoff(self.root, "agent/task", later)

    def test_admit_writes_nothing_when_managed_provenance_is_missing(self) -> None:
        head = self.managed_head()
        observed = {"number": 1, "state": "open", "base": {"ref": "main"}, "head": {"ref": "agent/task", "sha": head}}
        with patch.object(queue, "_repo", return_value=REPO), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_events", return_value=[]), \
             patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "_comments", return_value=[]), patch.object(queue, "trusted_apps", return_value=frozenset()), \
             patch.object(queue, "trusted_writers", return_value=frozenset()), \
             patch.object(queue, "_ensure_labels"), patch.object(queue, "_comment") as comment, \
             patch.object(queue, "_label") as label, patch.object(queue, "_transition") as transition:
            with self.assertRaisesRegex(queue.QueueError, "lacks valid exact task-content provenance"):
                queue.admit(self.root, 1, head)
        comment.assert_not_called()
        label.assert_not_called()
        transition.assert_not_called()

    def test_admit_writes_nothing_when_archived_evidence_is_malformed(self) -> None:
        head = self.managed_head()
        self.state()
        archive = self.root / "openspec/changes/archive/2026-10-05-sample"
        archive.mkdir(parents=True)
        (archive / "automated-checks.json").write_text('{"outcome":"success"}', encoding="utf-8")
        observed = {"number": 1, "state": "open", "base": {"ref": "main"}, "head": {"ref": "agent/task", "sha": head}}
        with patch.object(queue, "_repo", return_value=REPO), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_events", return_value=[]), \
             patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "_comments", return_value=[]), patch.object(queue, "trusted_apps", return_value=frozenset()), \
             patch.object(queue, "trusted_writers", return_value=frozenset()), \
             patch.object(queue, "_ensure_labels") as ensure_labels, patch.object(queue, "_comment") as comment, \
             patch.object(queue, "_label") as label, patch.object(queue, "_transition") as transition:
            with self.assertRaisesRegex(queue.QueueError, "archived verification evidence .* malformed"):
                queue.admit(self.root, 1, head)
        ensure_labels.assert_not_called()
        comment.assert_not_called()
        label.assert_not_called()
        transition.assert_not_called()

    def test_supplied_developer_handoff_is_unchanged(self) -> None:
        head = self.commit("feature.txt")
        identity = {"kind": "contribution", "change": "sample", "task_content": {"digest": "d"}}
        handoff = {"task_identity": identity, "gates": {}}
        observed = {"number": 1, "state": "open", "base": {"ref": "main"}, "head": {"ref": "agent/task", "sha": head}}
        with patch.object(queue, "_repo", return_value=REPO), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_events", side_effect=[[], [admission(1, 5, head)]]), patch.object(queue, "_main", return_value=BASE), \
             patch.object(queue, "_comments", return_value=[]), patch.object(queue, "trusted_apps", return_value=frozenset()), \
             patch.object(queue, "trusted_writers", return_value=frozenset()), patch.object(queue, "_derive", return_value={}), \
             patch.object(queue, "_latest", return_value={"state": "review-pending"}), \
             patch.object(queue, "_ensure_labels"), patch.object(queue, "_comment"), patch.object(queue, "_label"), \
             patch.object(queue, "publish_job"), patch.object(queue, "_transition") as transition, \
             patch.object(queue, "_admission_handoff") as derived:
            # contribution identity requires contribution_base; supply it.
            identity["contribution_base"] = BASE
            queue.admit(self.root, 1, head, handoff=handoff)
        derived.assert_not_called()
        self.assertEqual(transition.call_args.kwargs["task_identity"], identity)

    def test_integration_placeholder_identity_never_replaces_a_recorded_managed_identity(self) -> None:
        from candidate_lifecycle import build_handoff_record, marker_body

        managed = {"task_content": "m" * 64}
        prior = build_handoff_record(number=7, state="ready", head=HEAD, task_identity=managed, gates={},
                                     red_gate=None, not_reverified=[], attempts={}, next_job=None,
                                     at="2026-10-05T08:00:00Z")
        posted: list[str] = []
        observed = {"number": 7, "state": "open", "head": {"sha": HEAD}, "labels": []}
        with patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
             patch.object(queue, "_label"), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=[{"id": 1, "author_association": "OWNER", "body": marker_body(prior)}]), \
             patch.object(queue, "trusted_apps", return_value=frozenset()), patch.object(queue, "trusted_writers", return_value=frozenset()), \
             patch.object(queue.subprocess, "run", return_value=__import__("subprocess").CompletedProcess([], 0, "", "")):
            record = queue._transition(ROOT_PATH, REPO, 7, "integrating", HEAD,
                                       task_identity={"branch": "agent/7", "head": HEAD}, attempt="integration")
        self.assertEqual(record["task_identity"], managed)
        self.assertEqual(len(posted), 1)


class RequiredCheckObservationMappingTests(unittest.TestCase):
    """How the coordinator reacts to each classified required-check observation."""

    def run_worker(self, state: RequiredCheckState, *, polls: int = 0):
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(20, 1, admission(1, 20))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_label") as label, patch.object(queue, "_transition", return_value=None), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), \
             patch.object(queue, "_raise_if_owned_elsewhere"), \
             patch.object(queue, "CHECK_WAIT_SECONDS", 0), \
             patch.object(queue, "required_check_state_for_ref", return_value=state), \
             patch.object(queue, "_integration_repair", return_value={"state": "waiting", "number": 1}) as repair, \
             patch.object(queue, "_block", return_value={"state": "blocked", "number": 1}) as block, \
             patch.object(queue.subprocess, "run") as process:
            result = queue.worker(ROOT_PATH)
        process.assert_not_called()
        return result, block, repair, label

    def test_pending_waits_without_blocking(self) -> None:
        result, block, repair, _ = self.run_worker(RequiredCheckState("pending", checks=({"name": "validate"},)))
        self.assertEqual(result["state"], "waiting")
        self.assertEqual(result["reason"], "required CI pending")
        block.assert_not_called()
        repair.assert_not_called()

    def test_failed_enters_the_bounded_repair_not_a_block(self) -> None:
        result, block, repair, _ = self.run_worker(RequiredCheckState("failed", "validate"))
        self.assertEqual(result["state"], "waiting")
        block.assert_not_called()
        self.assertEqual(repair.call_args.args[-1].gate, "required-checks")

    def test_transport_and_head_mismatch_wait_naming_the_cause_and_release(self) -> None:
        for cause in ("transport", "head-mismatch"):
            with self.subTest(cause=cause):
                result, block, repair, label = self.run_worker(RequiredCheckState("unknown", "GitHub down", cause=cause))
                self.assertEqual(result["state"], "waiting")
                self.assertIn(cause, result["reason"])
                self.assertIn("GitHub down", result["reason"])
                block.assert_not_called()
                repair.assert_not_called()
                label.assert_any_call(ROOT_PATH, REPO, 1, queue.ACTIVE, present=False)

    def test_malformed_and_unsupported_state_still_block_visibly(self) -> None:
        for cause in ("malformed", "unsupported-state"):
            with self.subTest(cause=cause):
                result, block, _, _ = self.run_worker(RequiredCheckState("unknown", "bad output", cause=cause))
                self.assertEqual(result["state"], "blocked")
                self.assertIn(cause, block.call_args.args[3])
                self.assertIn("bad output", block.call_args.args[3])

    def test_unsupported_base_blocks_with_the_named_error(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(20, 1, admission(1, 20))]), \
             patch.object(queue, "_pr", return_value=pr(1)), patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_label"), patch.object(queue, "_transition", return_value=None), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), patch.object(queue, "_raise_if_owned_elsewhere"), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("unknown", "base release/1.0", cause="unsupported-state")), \
             patch.object(queue, "_block", return_value={"state": "blocked"}) as block:
            queue.worker(ROOT_PATH)
        self.assertIn("base release/1.0", block.call_args.args[3])


class ContributionRequiredChecksGateTests(unittest.TestCase):
    def test_contribution_to_requirement_branch_records_passed_gate_from_mains_validate(self) -> None:
        from subprocess import CompletedProcess
        from candidate_lifecycle import build_handoff_record, marker_body

        proof = {"version": 1, "digest": "d" * 64, "paths": {"a": "b"}, "base": BASE}
        identity = {"kind": "contribution", "change": "c", "requirement": "o/b#1", "source_issue": "o/b#2",
                    "target_branch": "requirement/BR-7", "contribution_base": BASE, "task_content": proof}
        record = build_handoff_record(number=7, state="ready", head=HEAD, task_identity=identity, gates={},
                                      red_gate=None, not_reverified=[], attempts={}, next_job=None,
                                      at="2026-10-05T08:00:00Z")
        calls: list[list[str]] = []

        def gh(command, **_kwargs):
            calls.append(command)
            if command[:3] == ["gh", "pr", "view"]:
                if "baseRefName" in command:
                    return CompletedProcess(command, 0, '{"baseRefName":"requirement/BR-7"}', "")
                return CompletedProcess(command, 0, json.dumps({"state": "OPEN", "headRefOid": HEAD}), "")
            if command[:2] == ["gh", "api"]:
                return CompletedProcess(command, 0, json.dumps({"name": "main", "protected": True, "protection": {"required_status_checks": {"contexts": ["validate"], "checks": []}}}), "")
            if command[:3] == ["gh", "pr", "checks"]:
                assert "--required" not in command
                return CompletedProcess(command, 0, json.dumps([
                    {"name": "validate", "state": "SUCCESS", "workflow": "Platform CI", "link": ""},
                    {"name": "publish-next", "state": "FAILURE", "workflow": "queue", "link": ""}]), "")
            raise AssertionError(command)

        observed = {**pr(7), "base": {"ref": "requirement/BR-7"}}
        with patch.object(queue, "_repo", return_value=REPO), patch.object(queue, "_pr", return_value=observed), \
             patch.object(queue, "_comments", return_value=[{"id": 1, "author_association": "OWNER", "body": marker_body(record)}]), \
             patch.object(queue, "trusted_apps", return_value=frozenset()), patch.object(queue, "trusted_writers", return_value=frozenset()), \
             patch("publication_state.run_github_with_retry", side_effect=gh):
            result = queue.candidate_status(ROOT_PATH, 7)
        self.assertEqual(result["gates"]["required-checks"]["result"], "passed")
        self.assertEqual(result["gates"]["required-checks"]["evidence"]["kind"], "passed")


if __name__ == "__main__":
    unittest.main()
