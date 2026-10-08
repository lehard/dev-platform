"""Coordinator configuration preflight: named failures, no secrets, no candidate observation."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import publication_queue as queue  # noqa: E402

REPO = "owner/repo"
CANARY = "ghs_CANARY_SECRET_TOKEN_VALUE"
CI_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "PREFLIGHT_APP_CLIENT_ID_SET": "true", "PREFLIGHT_APP_PRIVATE_KEY_SET": "true",
    "GITHUB_REPOSITORY": REPO, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
    "GH_TOKEN": CANARY, "DEV_PLATFORM_COORDINATOR_APP": "dev-platform-bot",
}
LOCAL_ENV = {"PATH": os.environ.get("PATH", "")}


class FakeGitHub:
    """Fake ``gh`` API keyed by endpoint; a value that is an Exception is raised."""

    def __init__(self, **overrides):
        self.calls: list[tuple[str, ...]] = []
        self.responses = {
            "repo": {"nameWithOwner": REPO},
            "pulls": [],
            "installation": {"repositories": [{"full_name": REPO}]},
            "repository": {"permissions": {"push": True}},
        }
        self.responses.update(overrides)

    def __call__(self, root, *args, data=None):
        self.calls.append(args)
        joined = " ".join(args)
        if args[:2] == ("repo", "view"):
            key = "repo"
        elif "installation/repositories" in joined:
            key = "installation"
        elif "/pulls" in joined:
            key = "pulls"
        else:
            key = "repository"
        value = self.responses[key]
        if isinstance(value, Exception):
            raise value
        return value


class PreflightFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.gh = FakeGitHub()
        for patcher in (
            patch.object(queue, "_gh", side_effect=lambda *a, **k: self.gh(*a, **k)),
            patch.object(queue, "read_platform_config", return_value={}),
            patch("_platform_common.read_project_config", return_value={}),
            patch("_platform_common.read_operator_config", return_value={}),
            patch.object(queue, "enabled", return_value=True),
            patch.dict(os.environ, {"DEV_PLATFORM_COORDINATOR_APP": CI_ENV["DEV_PLATFORM_COORDINATOR_APP"]}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_preflight(self, mode="ci", phase="all", env=None):
        return queue.preflight(Path("/unused"), mode, phase, CI_ENV if env is None and mode == "ci" else (env or LOCAL_ENV))

    def failed(self, result):
        self.assertEqual(result["state"], "error")
        return result["checks"][-1]


class CiPreflightTests(PreflightFixture):
    def test_valid_configuration_passes_all_phases(self):
        for phase in ("inputs", "runtime", "all"):
            with self.subTest(phase=phase):
                result = self.run_preflight("ci", phase)
                self.assertEqual(result["state"], "ok", result)
                self.assertTrue(all(check["status"] == "ok" for check in result["checks"]))

    def test_each_missing_input_is_named(self):
        for name in ("PREFLIGHT_APP_CLIENT_ID_SET", "PREFLIGHT_APP_PRIVATE_KEY_SET", "GITHUB_REPOSITORY",
                     "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            for broken in ("", "false") if name.startswith("PREFLIGHT") else ("", "x y"):
                with self.subTest(name=name, value=broken):
                    result = self.run_preflight("ci", "inputs", {**CI_ENV, name: broken})
                    self.assertEqual(self.failed(result)["name"], name)
                    self.assertEqual(self.gh.calls, [])

    def test_missing_tool_is_named(self):
        with patch("shutil.which", side_effect=lambda tool, path=None: None if tool == "gh" else "/bin/" + tool):
            self.assertEqual(self.failed(self.run_preflight("ci", "inputs"))["name"], "tool:gh")

    def test_empty_token_and_slug_are_named(self):
        self.assertEqual(self.failed(self.run_preflight("ci", "runtime", {**CI_ENV, "GH_TOKEN": ""}))["name"], "GH_TOKEN")
        env = {**CI_ENV, "DEV_PLATFORM_COORDINATOR_APP": ""}
        self.assertEqual(self.failed(self.run_preflight("ci", "runtime", env))["name"], "DEV_PLATFORM_COORDINATOR_APP")
        env = {**CI_ENV, "DEV_PLATFORM_COORDINATOR_APP": "bad slug!"}
        self.assertEqual(self.failed(self.run_preflight("ci", "runtime", env))["name"], "DEV_PLATFORM_COORDINATOR_APP")
        self.assertEqual(self.gh.calls, [])

    def test_environment_and_configured_slug_contradiction(self):
        config = {"publication": {"coordinator_app": "other-app"}}
        with patch("_platform_common.read_project_config", return_value=config):
            check = self.failed(self.run_preflight("ci", "runtime"))
        self.assertEqual(check["name"], "coordinator App identity")
        self.assertIn("environment names dev-platform-bot", check["detail"])
        self.assertIn("other-app", check["detail"])
        self.assertEqual(self.gh.calls, [])

    def test_unreadable_trust_configuration_is_named(self):
        with patch("_platform_common.read_project_config", side_effect=ValueError("bad toml")):
            check = self.failed(self.run_preflight("ci", "runtime"))
        self.assertIn(".dev-platform.toml", check["detail"] + check["name"])
        self.assertEqual(self.gh.calls, [])

    def test_disabled_coordinator_and_repository_mismatch(self):
        with patch.object(queue, "enabled", return_value=False):
            self.assertEqual(self.failed(self.run_preflight("ci", "runtime"))["name"], "coordinator-enabled")
        self.gh.responses["repo"] = {"nameWithOwner": "owner/other"}
        self.assertEqual(self.failed(self.run_preflight("ci", "runtime"))["name"], "GITHUB_REPOSITORY")

    def test_token_must_be_an_installation_token_for_exactly_this_repository(self):
        for repositories in ([], [{"full_name": "owner/other"}], [{"full_name": REPO}, {"full_name": "owner/other"}]):
            with self.subTest(repositories=repositories):
                self.gh.responses["installation"] = {"repositories": repositories}
                self.assertEqual(self.failed(self.run_preflight("ci", "runtime"))["name"], "installation-token")

    def test_bot_permission_never_asks_the_collaborator_api(self):
        result = self.run_preflight("ci", "runtime")
        self.assertEqual(result["state"], "ok")
        self.assertIn({"name": "bot-permission", "status": "ok",
                       "detail": "contents and pull-requests write granted at token mint"}, result["checks"])
        self.assertFalse(any("/collaborators/" in " ".join(call) for call in self.gh.calls))

    def test_probe_failures_use_fixed_categories_without_response_text(self):
        for message, category in (("HTTP 401: Bad credentials", "unauthorized"), ("HTTP 404: Not Found", "not-found"),
                                  ("dial tcp: connection refused", "unreachable")):
            with self.subTest(category=category):
                self.gh.responses["pulls"] = queue.QueueError(f"{message} {CANARY}")
                result = self.run_preflight("ci", "runtime")
                check = self.failed(result)
                self.assertEqual(check["name"], "pulls-read")
                self.assertTrue(check["detail"].endswith(category))
                self.assertNotIn(CANARY, json.dumps(result))

    def test_canary_never_appears_in_any_output(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(queue, "current_worktree_root", return_value=Path("/unused")), \
                patch.object(sys, "argv", ["publication_queue.py", "preflight", "--mode", "ci", "--phase", "runtime"]), \
                patch.dict(os.environ, CI_ENV), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(queue.main(), 0)
        self.assertNotIn(CANARY, out.getvalue() + err.getvalue())
        self.gh.responses["installation"] = queue.QueueError(f"boom {CANARY}")
        out = io.StringIO()
        with patch.object(queue, "current_worktree_root", return_value=Path("/unused")), \
                patch.object(sys, "argv", ["publication_queue.py", "preflight", "--mode", "ci", "--phase", "all"]), \
                patch.dict(os.environ, CI_ENV), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(queue.main(), 2)
        self.assertNotIn(CANARY, out.getvalue() + err.getvalue())
        self.assertEqual(json.loads(out.getvalue())["state"], "error")

    def test_mode_and_phase_are_required_and_validated(self):
        with self.assertRaises(queue.QueueError):
            queue.preflight(Path("/unused"), "auto", "all", CI_ENV)
        for argv in (["preflight", "--mode", "ci"], ["preflight", "--phase", "all"], ["worker"]):
            with self.subTest(argv=argv), patch.object(sys, "argv", ["publication_queue.py", *argv]), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                queue.main()
            self.assertEqual(raised.exception.code, 2)


class LocalPreflightTests(PreflightFixture):
    def setUp(self) -> None:
        super().setUp()
        patcher = patch.dict(os.environ, {"DEV_PLATFORM_COORDINATOR_APP": ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = {"publication": {"coordinator_app": "dev-platform-bot"}}
        for config in (patch.object(queue, "read_platform_config", return_value=self.config),
                       patch("_platform_common.read_project_config", return_value=self.config)):
            config.start()
            self.addCleanup(config.stop)

    def test_valid_local_run(self):
        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            result = self.run_preflight("local", "all")
        self.assertEqual(result["state"], "ok", result)

    def test_gh_auth_failure_and_missing_configuration(self):
        with patch("subprocess.run") as run:
            run.return_value.returncode = 1
            self.assertEqual(self.failed(self.run_preflight("local", "inputs"))["name"], "gh-auth")
        with patch.object(queue, "read_platform_config", return_value={}), \
                patch("_platform_common.read_project_config", return_value={}):
            self.assertEqual(self.failed(self.run_preflight("local", "runtime"))["name"], "[publication] coordinator_app")

    def test_push_permission_is_required(self):
        self.gh.responses["repository"] = {"permissions": {"push": False}}
        self.assertEqual(self.failed(self.run_preflight("local", "runtime"))["name"], "repository-permission")


class WorkerPreflightGateTests(PreflightFixture):
    def test_failing_preflight_never_observes_a_candidate(self):
        env = {**CI_ENV, "PREFLIGHT_APP_PRIVATE_KEY_SET": "false"}
        with patch.object(queue, "_queued") as queued, patch.object(queue, "_repo") as repo:
            result = queue.run_worker(Path("/unused"), "ci", env, install_sink=False)
        self.assertEqual(result["state"], "error")
        queued.assert_not_called()
        repo.assert_not_called()

    def test_passing_preflight_installs_identity_and_runs_worker(self):
        with patch.object(queue, "worker", return_value={"state": "empty"}) as run, \
                patch.object(queue, "use_default_friction_sink") as sink:
            result = queue.run_worker(Path("/unused"), "ci", CI_ENV, install_sink=True)
        self.assertEqual(result, {"state": "empty"})
        run.assert_called_once()
        self.assertEqual(sink.call_args.kwargs["worker"], f"github-actions:{REPO}:123:2")

    def test_worker_exit_code_follows_the_outcome(self):
        for state, code in (("contribution-integrated", 0), ("discarded", 0), ("repair-pending", 0),
                            ("integration-repair-pending", 0), ("merged", 0), ("blocked", 2), ("error", 2)):
            with self.subTest(state=state), \
                    patch.object(queue, "run_worker", return_value={"state": state}), \
                    patch.object(queue, "current_worktree_root", return_value=Path("/unused")), \
                    patch.object(sys, "argv", ["publication_queue.py", "worker", "--mode", "ci"]), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(queue.main(), code)

    def test_local_identity_is_unique_per_run(self):
        first, second = (queue.run_identity("local", {}) for _ in range(2))
        self.assertTrue(first.startswith("local:"))
        self.assertNotEqual(first, second)


class WorkflowStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        text = (ROOT / ".github" / "workflows" / "publication-queue.yml").read_text(encoding="utf-8")
        self.steps = yaml.safe_load(text)["jobs"]["publish-next"]["steps"]

    def index(self, fragment: str) -> int:
        return next(i for i, step in enumerate(self.steps)
                    if fragment in str(step.get("run", "")) or fragment in str(step.get("uses", "")))

    def test_preflight_order_around_the_token_step(self):
        inputs = self.index("preflight --mode ci --phase inputs")
        token = self.index("actions/create-github-app-token")
        runtime = self.index("preflight --mode ci --phase runtime")
        worker = self.index("publication_queue.py worker --mode ci")
        self.assertLess(inputs, token)
        self.assertLess(token, runtime)
        self.assertLess(runtime, worker)

    def test_inputs_step_receives_only_boolean_presence_flags(self):
        env = self.steps[self.index("preflight --mode ci --phase inputs")]["env"]
        self.assertEqual(set(env), {"PREFLIGHT_APP_CLIENT_ID_SET", "PREFLIGHT_APP_PRIVATE_KEY_SET"})
        for value in env.values():
            self.assertRegex(value, r"^\$\{\{ (vars|secrets)\.[A-Z_]+ != '' \}\}$")

    def test_worker_step_carries_every_input_its_full_preflight_reads(self):
        # ``worker --mode ci`` repeats the full (inputs + runtime) preflight in its own step.
        worker = self.steps[self.index("publication_queue.py worker --mode ci")]["env"]
        inputs = self.steps[self.index("preflight --mode ci --phase inputs")]["env"]
        runtime = self.steps[self.index("preflight --mode ci --phase runtime")]["env"]
        self.assertEqual({name: worker.get(name) for name in inputs}, inputs)
        self.assertEqual({name: worker.get(name) for name in runtime}, runtime)

    def test_source_contract_is_installed_before_any_preflight(self):
        install = self.index("cp dev-platform/source-contract.toml .dev-platform.toml")
        self.assertIn("test ! -e .dev-platform.toml", self.steps[install]["run"])
        self.assertLess(install, self.index("preflight --mode ci --phase inputs"))

    def test_tracked_source_contract_selects_the_coordinator_without_operator_state(self):
        import tomllib

        from _platform_common import lifecycle_mode

        with (ROOT / "dev-platform" / "source-contract.toml").open("rb") as fh:
            contract = tomllib.load(fh)
        self.assertEqual("source", contract["platform_version"])
        self.assertEqual("coordinator", lifecycle_mode(contract))
        self.assertFalse({"operator", "development_backlog", "private_lineage"} & set(contract))

    def test_token_permissions_stay_least_privilege(self):
        options = self.steps[self.index("actions/create-github-app-token")]["with"]
        self.assertEqual({k for k in options if k.startswith("permission-")},
                         {"permission-contents", "permission-pull-requests"})
        self.assertEqual(options["permission-contents"], "write")
        self.assertEqual(options["permission-pull-requests"], "write")


if __name__ == "__main__":
    unittest.main()
