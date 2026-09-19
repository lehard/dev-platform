from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"


def load_module():
    import sys
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("gitlab_delivery_test", SCRIPTS / "gitlab_delivery.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gitlab_delivery = load_module()


class GitLabDeliveryTests(unittest.TestCase):
    def test_publish_reuses_exact_branch_mr_and_stops_at_human_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            responses = [
                subprocess.CompletedProcess([], 0, json.dumps([{"iid": 7, "web_url": "https://gitlab.example/mr/7"}]), ""),
                subprocess.CompletedProcess([], 0, json.dumps({"iid": 7, "web_url": "https://gitlab.example/mr/7", "source_branch": "task/public-core", "target_branch": "main", "sha": "abc123"}), ""),
                subprocess.CompletedProcess([], 0, json.dumps([{"sha": "abc123", "status": "success"}]), ""),
            ]
            with mock.patch.object(gitlab_delivery, "read_platform_config", return_value={"main_branch": "main"}), \
                 mock.patch.object(gitlab_delivery, "_branch", return_value="task/public-core"), \
                 mock.patch.object(gitlab_delivery, "_clean"), \
                 mock.patch.object(gitlab_delivery, "run_git", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "abc123\n", "")]) as run_git, \
                 mock.patch.object(gitlab_delivery, "_glab", side_effect=responses) as glab:
                self.assertEqual(gitlab_delivery.publish(root, title=None, body=None), 0)
            self.assertEqual(run_git.call_args_list[0].args[0], ["push", "-u", "origin", "task/public-core:task/public-core"])
            self.assertEqual(glab.call_args_list[0].args[1][:2], ["mr", "list"])
            self.assertEqual(glab.call_args_list[1].args[1][:2], ["mr", "view"])
            self.assertEqual(glab.call_args_list[2].args[1][:2], ["mr", "pipelines"])
            self.assertFalse(any(call.args[1][:2] == ["mr", "merge"] for call in glab.call_args_list))

    def test_publish_rejects_merge_request_head_mismatch(self) -> None:
        root = Path(".")
        responses = [
            subprocess.CompletedProcess([], 0, json.dumps([{"iid": 7}]), ""),
            subprocess.CompletedProcess([], 0, json.dumps({"iid": 7, "source_branch": "task/public-core", "target_branch": "main", "sha": "other"}), ""),
        ]
        with mock.patch.object(gitlab_delivery, "read_platform_config", return_value={"main_branch": "main"}), \
             mock.patch.object(gitlab_delivery, "_branch", return_value="task/public-core"), \
             mock.patch.object(gitlab_delivery, "_clean"), \
             mock.patch.object(gitlab_delivery, "run_git", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "abc123\n", "")]), \
             mock.patch.object(gitlab_delivery, "_glab", side_effect=responses):
            with self.assertRaisesRegex(SystemExit, "exact published task HEAD"):
                gitlab_delivery.publish(root, title=None, body=None)

    def test_publish_returns_resumable_for_running_exact_head_pipeline(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 0, json.dumps([{"iid": 7}]), ""),
            subprocess.CompletedProcess([], 0, json.dumps({"iid": 7, "source_branch": "task/public-core", "target_branch": "main", "sha": "abc123"}), ""),
            subprocess.CompletedProcess([], 0, json.dumps([{"sha": "abc123", "status": "running"}]), ""),
        ]
        with mock.patch.object(gitlab_delivery, "read_platform_config", return_value={"main_branch": "main"}), \
             mock.patch.object(gitlab_delivery, "_branch", return_value="task/public-core"), \
             mock.patch.object(gitlab_delivery, "_clean"), \
             mock.patch.object(gitlab_delivery, "run_git", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "abc123\n", "")]), \
             mock.patch.object(gitlab_delivery, "_glab", side_effect=responses):
            self.assertEqual(gitlab_delivery.publish(Path("."), title=None, body=None), 3)

    def test_publish_rejects_non_green_or_unprovable_pipeline_evidence(self) -> None:
        for label, pipeline in (
            ("failed", [{"sha": "abc123", "status": "failed"}]),
            ("canceled", [{"sha": "abc123", "status": "canceled"}]),
            ("skipped", [{"sha": "abc123", "status": "skipped"}]),
            ("missing", []),
            ("ambiguous", [{"sha": "abc123", "status": "success"}, {"sha": "abc123", "status": "success"}]),
        ):
            with self.subTest(label=label):
                responses = [
                    subprocess.CompletedProcess([], 0, json.dumps([{"iid": 7}]), ""),
                    subprocess.CompletedProcess([], 0, json.dumps({"iid": 7, "source_branch": "task/public-core", "target_branch": "main", "sha": "abc123"}), ""),
                    subprocess.CompletedProcess([], 0, json.dumps(pipeline), ""),
                ]
                with mock.patch.object(gitlab_delivery, "read_platform_config", return_value={"main_branch": "main"}), \
                     mock.patch.object(gitlab_delivery, "_branch", return_value="task/public-core"), \
                     mock.patch.object(gitlab_delivery, "_clean"), \
                     mock.patch.object(gitlab_delivery, "run_git", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "abc123\n", "")]), \
                     mock.patch.object(gitlab_delivery, "_glab", side_effect=responses):
                    with self.assertRaises(SystemExit):
                        gitlab_delivery.publish(Path("."), title=None, body=None)

    def test_publish_rejects_unreadable_pipeline_evidence(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 0, json.dumps([{"iid": 7}]), ""),
            subprocess.CompletedProcess([], 0, json.dumps({"iid": 7, "source_branch": "task/public-core", "target_branch": "main", "sha": "abc123"}), ""),
            subprocess.CompletedProcess([], 1, "", "forbidden"),
        ]
        with mock.patch.object(gitlab_delivery, "read_platform_config", return_value={"main_branch": "main"}), \
             mock.patch.object(gitlab_delivery, "_branch", return_value="task/public-core"), \
             mock.patch.object(gitlab_delivery, "_clean"), \
             mock.patch.object(gitlab_delivery, "run_git", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "abc123\n", "")]), \
             mock.patch.object(gitlab_delivery, "_glab", side_effect=responses):
            with self.assertRaisesRegex(SystemExit, "unreadable"):
                gitlab_delivery.publish(Path("."), title=None, body=None)


if __name__ == "__main__":
    unittest.main()
