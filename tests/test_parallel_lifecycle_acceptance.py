"""Parallel lifecycle acceptance: the offline sandbox scenario and its local GitHub adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
import parallel_lifecycle_acceptance as acceptance  # noqa: E402


def scenario_process(output: Path, *extra: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(SCRIPTS / "parallel_lifecycle_acceptance.py"), "run",
                             "--output", str(output), *extra], cwd=output.parent, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class ScenarioTests(unittest.TestCase):
    def test_scenario_runs_twice_with_the_same_lifecycle_and_no_manual_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = [Path(tmp) / "first", Path(tmp) / "second"]
            processes = [scenario_process(output) for output in outputs]  # two separate roots, concurrently
            results = [process.communicate(timeout=300) for process in processes]
            for process, (stdout, stderr) in zip(processes, results):
                self.assertEqual(process.returncode, 0, stderr)
            runs = [json.loads((output / "summary.json").read_text()) for output in outputs]
            first, second = runs
            self.assertEqual(first["transitions"], second["transitions"])  # same kinds, attempts, order
            self.assertEqual(first["merge_operations"], second["merge_operations"])
            for run in runs:
                self.assertEqual(run["merged"], {"A": True, "B": True, "C": True})
                self.assertEqual(run["admitted_states"], {"A": "review-pending", "B": "review-pending", "C": "review-pending"})
                # Every candidate is ready before the first merge: the candidates were simultaneously active.
                self.assertEqual(set(run["states_before_first_merge"].values()), {"ready"})
                self.assertEqual([m for m in run["merge_operations"] if m[1] == "merge"],
                                 [["A", "merge"], ["B", "merge"], ["C", "merge"]])
                self.assertIn(["B", "update-branch"], run["merge_operations"])  # main moved under B
                self.assertNotEqual(run["initial_main"], run["final_main"])
                states = {tuple(event[:3]) for event in run["transitions"]}
                self.assertIn(("B", "record", "repair-pending"), states)        # review finding
                self.assertIn(("B", "record", "reviewing"), states)             # fresh review of the repair
                self.assertIn(("B", "record", "finalize-pending"), states)
                self.assertIn(("C", "record", "integration-repair-pending"), states)
                self.assertIn(("A", "record", "merged"), states)
                repairs = [e for e in run["transitions"] if e[1] == "result" and e[2].startswith("repair")]
                self.assertIn("pushed", [e[4] for e in repairs])
                reviews = [e for e in run["transitions"] if e[:2] == ["B", "claim"] and e[2].startswith("review")]
                self.assertEqual(len(reviews), 2)  # initial review and the repeat review after repair
                worker_names = {e[4] for e in run["transitions"] if e[1] == "claim"}
                self.assertGreater(len(worker_names), 3)  # separate workers claimed jobs
                self.assertEqual(run["operator_actions"], [])  # no operator repair, finish or archive action
                self.assertEqual([a["candidate"] for a in run["developer_actions"]],
                                 ["agent/br-353-t2-b", "agent/br-353-t3-c"])  # content-bound handoff after repair
                self.assertEqual({a["action"] for a in run["developer_actions"]}, {"semantic-verification-handoff"})
                claims = [e[2].split(":")[0] for e in run["transitions"] if e[:2] == ["C", "claim"]]
                self.assertEqual(claims.count("review"), 2)  # the finalized C is reviewed again after integration repair
                self.assertEqual(claims.count("finalize"), 3)  # initial, blocked on semantic handoff, final
                self.assertEqual(acceptance.structure_problems(run), [])
                self.assertEqual(run["unsupported_gh_calls"], [])
                self.assertEqual(acceptance.post_merge_problems(run["transitions"]), [])
                self.assertTrue(run["containment"]["source_unchanged"])
                self.assertEqual(run["containment"]["sandboxes_verified_and_removed"], ["coordinator", "author"])
            for output in outputs:
                self.assertFalse((output / "sandbox/coordinator").exists())
                self.assertTrue((output / "trace.json").is_file())

    def test_exhausted_action_bound_fails_the_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            process = scenario_process(Path(tmp) / "bounded", "--max-actions", "2")
            _, stderr = process.communicate(timeout=300)
            self.assertEqual(process.returncode, 1)
            self.assertIn("execution bound exhausted", stderr)

    def test_operator_actions_are_observed_at_the_adapter_and_fail_the_structure_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            github = acceptance.LocalGitHub(Path(tmp), acceptance.REPO)
            github.add_pr(1, "agent/one")
            post = ["api", "-X", "POST", f"repos/{acceptance.REPO}/issues/1/comments", "-f", "body=manual"]
            github.run(post)
            self.assertEqual(github.operator_actions, [])  # automation and developer actions are not operator actions
            github.actor = "operator"
            github.run(["repo", "view", "--json", "nameWithOwner"])  # a read is not an action
            self.assertEqual(github.operator_actions, [])
            github.run(post)
            self.assertEqual(len(github.operator_actions), 1)
            summary = {"unsupported_gh_calls": [], "merged": {}, "states_before_first_merge": {}, "transitions": [],
                       "merge_operations": [], "operator_actions": github.operator_actions}
            self.assertTrue(any("operator completion actions" in p for p in acceptance.structure_problems(summary)))

    def test_failed_run_still_cleans_sandboxes_and_records_the_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bounded"
            process = scenario_process(output, "--max-actions", "2")
            process.communicate(timeout=300)
            summary = json.loads((output / "summary.json").read_text())
            self.assertIn("execution bound exhausted", summary["failure"])
            self.assertTrue(summary["containment"]["source_unchanged"])
            self.assertFalse((output / "sandbox/coordinator").exists())

    def test_missing_post_merge_result_is_reported(self):
        transitions = [[letter, "result", f"{kind}:a0", "h1", "done", None]
                       for letter in ("A", "B", "C") for kind in ("retrospective", "cleanup")]
        problems = acceptance.post_merge_problems(transitions)
        self.assertTrue(any("terminal-reconciliation for A did not complete" in p for p in problems))
        self.assertTrue(any("did not reconcile the Requirement" in p for p in problems))
        transitions += [[letter, "result", "terminal-reconciliation:a0", "h1", "blocked", None] for letter in "ABC"]
        self.assertTrue(any("terminal-reconciliation for B" in p for p in acceptance.post_merge_problems(transitions)))


class LocalGitHubTests(unittest.TestCase):
    """The adapter observes real Git refs and refuses what a protected GitHub would refuse."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.dict(os.environ, {**acceptance.IDENTITY, "GIT_CONFIG_GLOBAL": os.devnull,
                                              "GIT_CONFIG_NOSYSTEM": "1"})
        patch.start()
        self.addCleanup(patch.stop)
        root = Path(self.tmp.name)
        acceptance.build_seed(root / "seed")
        acceptance.git(root, "clone", "-q", "--bare", str(root / "seed"), str(root / "remote.git"))
        self.work = root / "work"
        acceptance.git(root, "clone", "-q", str(root / "remote.git"), str(self.work))
        self.remote = root / "remote.git"
        self.github = acceptance.LocalGitHub(self.remote, acceptance.REPO)
        self.head = self.branch("agent/one", "shared.py", "VALUE = 9\n")
        self.github.add_pr(1, "agent/one")

    def branch(self, name: str, path: str, text: str) -> str:
        acceptance.git(self.work, "checkout", "-q", "-B", name, "origin/main")
        acceptance.put(self.work / path, text)
        head = acceptance.commit_all(self.work, f"change {name}")
        acceptance.git(self.work, "push", "-q", "-f", "origin", f"HEAD:refs/heads/{name}")
        return head

    def move_main(self) -> None:
        acceptance.git(self.work, "checkout", "-q", "-B", "main", "origin/main")
        acceptance.put(self.work / "other.py", "x = 1\n")
        acceptance.commit_all(self.work, "main moves")
        acceptance.git(self.work, "push", "-q", "origin", "HEAD:refs/heads/main")

    def call(self, *argv: str) -> tuple[int, str, str]:
        return self.github.run(list(argv))

    def merge(self, head: str) -> tuple[int, str, str]:
        return self.call("pr", "merge", "1", "--squash", "--match-head-commit", head)

    def test_pr_head_is_observed_from_git_and_pushes_are_followed(self):
        code, out, _ = self.call("api", f"repos/{acceptance.REPO}/pulls/1")
        self.assertEqual((code, json.loads(out)["head"]["sha"]), (0, self.head))
        moved = self.branch("agent/one", "shared.py", "VALUE = 10\n")
        self.assertEqual(json.loads(self.call("api", f"repos/{acceptance.REPO}/pulls/1")[1])["head"]["sha"], moved)
        self.assertEqual(acceptance.git(self.remote, "rev-parse", "refs/pull/1/head"), moved)

    def test_merge_requires_the_exact_head_passing_checks_and_a_current_base(self):
        stale = self.head
        moved = self.branch("agent/one", "shared.py", "VALUE = 10\n")
        code, _, err = self.merge(stale)  # a head from before the push
        self.assertEqual(code, 1)
        self.assertIn("Head branch was modified", err)
        self.move_main()
        code, _, err = self.merge(moved)
        self.assertEqual(code, 1)
        self.assertIn("Base branch was modified", err)
        self.assertFalse(self.github.prs["1"]["merged"])
        before = acceptance.git(self.remote, "rev-parse", "refs/heads/main")
        code, _, _ = self.call("api", "-X", "PUT", f"repos/{acceptance.REPO}/pulls/1/update-branch",
                               "-f", f"expected_head_sha={moved}")
        self.assertEqual(code, 0)
        updated = acceptance.git(self.remote, "rev-parse", "refs/heads/agent/one")
        self.assertNotEqual(updated, moved)
        self.assertEqual(self.merge(updated)[0], 0)
        self.assertTrue(self.github.prs["1"]["merged"])
        self.assertNotEqual(acceptance.git(self.remote, "rev-parse", "refs/heads/main"), before)
        self.assertEqual(acceptance.git(self.remote, "show", "main:shared.py"), "VALUE = 10")

    def test_failing_checks_block_the_merge_and_checks_never_carry_to_another_head(self):
        bad = self.branch("agent/one", "shared.py", "<" * 7 + " conflict\n")
        code, out, _ = self.call("pr", "checks", "1", "--required", "--json", "name,state")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)[0]["state"], "FAILURE")
        code, _, err = self.merge(bad)
        self.assertEqual(code, 1)
        self.assertIn("checks have not passed", err)
        fixed = self.branch("agent/one", "shared.py", "VALUE = 3\n")
        self.assertEqual(self.call("pr", "checks", "1", "--required", "--json", "name,state")[0], 0)
        self.assertIn(bad, self.github.checks)
        self.assertTrue(self.github.checks[fixed])

    def test_update_branch_rejects_a_stale_expected_head_and_conflicts(self):
        stale = self.head
        self.branch("agent/one", "shared.py", "VALUE = 10\n")
        code, _, err = self.call("api", "-X", "PUT", f"repos/{acceptance.REPO}/pulls/1/update-branch",
                                 "-f", f"expected_head_sha={stale}")
        self.assertEqual(code, 1)
        self.assertIn("expected head sha", err)
        acceptance.git(self.work, "checkout", "-q", "-B", "main", "origin/main")
        acceptance.put(self.work / "shared.py", "VALUE = 99\n")
        acceptance.commit_all(self.work, "main edits the same line")
        acceptance.git(self.work, "push", "-q", "origin", "HEAD:refs/heads/main")
        head = acceptance.git(self.remote, "rev-parse", "refs/heads/agent/one")
        code, _, err = self.call("api", "-X", "PUT", f"repos/{acceptance.REPO}/pulls/1/update-branch",
                                 "-f", f"expected_head_sha={head}")
        self.assertEqual(code, 1)
        self.assertIn("merge conflict", err)
        self.assertEqual(acceptance.git(self.remote, "rev-parse", "refs/heads/agent/one"), head)

    def test_unsupported_calls_fail_and_are_recorded(self):
        for argv in (["issue", "list"], ["api", "repos/other/repo/pulls/1"], ["api", f"repos/{acceptance.REPO}/rulesets"],
                     ["pr", "merge", "1", "--rebase", "--match-head-commit", self.head]):
            code, _, _ = self.call(*argv)
            self.assertNotEqual(code, 0, argv)
        self.assertEqual([c.get("unsupported") for c in self.github.calls[:3]], [True, True, True])

    def test_comments_and_labels_follow_github_semantics(self):
        post = ["api", "-X", "POST", f"repos/{acceptance.REPO}/issues/1/comments", "-f", "body=hello"]
        self.assertEqual(self.call(*post)[0], 0)
        listed = json.loads(self.call("api", f"repos/{acceptance.REPO}/issues/1/comments?per_page=100")[1])
        self.assertEqual([(c["body"], c["author_association"]) for c in listed], [("hello", "OWNER")])
        self.assertEqual(self.call("api", "-X", "DELETE", f"repos/{acceptance.REPO}/issues/1/labels/missing")[0], 1)
        self.assertEqual(self.call("api", "-X", "POST", f"repos/{acceptance.REPO}/issues/1/labels",
                                   "-f", "labels[]=publication:queued")[0], 0)
        queued = json.loads(self.call("pr", "list", "--state", "all", "--label", "publication:queued",
                                      "--json", "number,labels")[1])
        self.assertEqual([row["number"] for row in queued], [1])
        self.assertEqual(self.call("api", "-X", "DELETE",
                                   f"repos/{acceptance.REPO}/issues/1/labels/publication%3Aqueued")[0], 0)


class SnapshotTests(unittest.TestCase):
    def test_tree_digest_covers_content_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            acceptance.put(path, "x\n")
            before, mode = acceptance.tree_digest(Path(tmp)), path.stat().st_mode
            path.chmod(0o755)
            self.assertNotEqual(acceptance.tree_digest(Path(tmp)), before)
            path.chmod(mode)
            self.assertEqual(acceptance.tree_digest(Path(tmp)), before)
            acceptance.put(path, "y\n")
            self.assertNotEqual(acceptance.tree_digest(Path(tmp)), before)


if __name__ == "__main__":
    unittest.main()
