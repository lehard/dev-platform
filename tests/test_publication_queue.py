from __future__ import annotations

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


def admission(number: int, key: int, head: str = HEAD) -> dict:
    return {"version": 1, "number": number, "kind": "admit", "comment_id": key,
            "head": head, "base": BASE, "branch": f"agent/{number}"}


def pr(number: int, head: str = HEAD, labels: tuple[str, ...] = ()) -> dict:
    return {"number": number, "state": "open", "merged": False,
            "base": {"ref": "main"}, "head": {"ref": f"agent/{number}", "sha": head},
            "labels": [{"name": label} for label in labels]}


class AdmissionTests(unittest.TestCase):
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

    def test_failed_required_check_blocks_before_merge(self) -> None:
        with patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_queued", return_value=[(20, 1, admission(1, 20))]), \
             patch.object(queue, "_pr", return_value=pr(1)), \
             patch.object(queue, "_label"), \
             patch.object(queue, "_prepare", return_value=(HEAD, BASE)), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("failed", "validate")), \
             patch.object(queue, "_block", return_value={"state": "blocked"}) as block, \
             patch.object(queue.subprocess, "run") as process:
            self.assertEqual(queue.worker(ROOT_PATH)["state"], "blocked")
        block.assert_called_once()
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

    def test_conflicting_main_path_blocks_before_branch_update(self) -> None:
        from subprocess import CompletedProcess
        def git(args: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if args[0] == "merge-base":
                return CompletedProcess(args, 0, "", "")
            if args[0] == "diff":
                return CompletedProcess(args, 0, "task.py\n", "")
            return CompletedProcess(args, 0, "", "")
        with patch.object(queue, "_events", return_value=[admission(1, 20)]), \
             patch.object(queue, "_main", return_value=NEW_HEAD), \
             patch.object(queue, "run_git", side_effect=git), \
             patch.object(queue, "_task_paths", return_value={"task.py"}), \
             patch.object(queue, "_gh") as gh:
            with self.assertRaisesRegex(queue.QueueError, "main changed task paths"):
                queue._prepare(ROOT_PATH, REPO, 1, admission(1, 20), pr(1))
        gh.assert_not_called()


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


if __name__ == "__main__":
    unittest.main()
