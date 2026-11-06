from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import _platform_common as common  # noqa: E402
import lifecycle_workers as workers  # noqa: E402
import pr_review_gate as gate  # noqa: E402
import worker_credentials as wc  # noqa: E402

SECRET = "file-secret-value"
EXPORTED = "exported-secret-value"


class Base(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name)

    def operator(self, *, content: str | None = SECRET) -> dict:
        path = self.tmp / "token"
        if content is not None:
            path.write_text(content)
            path.chmod(0o600)
        return {"operator": {"enabled": True},
                "independent_review": {"login": {"claude": {"token_file": str(path)}}}}


class PlacementTests(Base):
    def test_operator_reads_the_file_without_an_export(self):
        self.assertEqual(wc.resolve_claude_token(self.operator(), {}), SECRET)

    def test_export_never_replaces_the_operator_file(self):
        with self.assertRaisesRegex(wc.CredentialError, "not readable") as error:
            wc.resolve_claude_token(self.operator(content=None), {wc.TOKEN_ENV: EXPORTED})
        self.assertNotIn(EXPORTED, str(error.exception))
        with self.assertRaisesRegex(wc.CredentialError, r"token_file is missing"):
            wc.resolve_claude_token({"operator": {"enabled": True}}, {wc.TOKEN_ENV: EXPORTED})

    def test_operator_file_wins_over_an_export(self):
        self.assertEqual(wc.resolve_claude_token(self.operator(), {wc.TOKEN_ENV: EXPORTED}), SECRET)

    def test_hosted_takes_only_the_job_secret(self):
        self.assertEqual(wc.resolve_claude_token({}, {wc.TOKEN_ENV: EXPORTED}), EXPORTED)
        for env in ({}, {wc.TOKEN_ENV: ""}, {wc.TOKEN_ENV: "  "}):
            with self.assertRaisesRegex(wc.CredentialError, wc.TOKEN_ENV):
                wc.resolve_claude_token({}, env)

    def test_disabled_operator_is_the_hosted_placement(self):
        config = {**self.operator(), "operator": {"enabled": False}}
        self.assertEqual(wc.resolve_claude_token(config, {wc.TOKEN_ENV: EXPORTED}), EXPORTED)

    def test_ambient_token_is_removed_only_on_the_operator_node(self):
        env = {wc.TOKEN_ENV: EXPORTED}
        wc.remove_ambient_token({}, env)
        self.assertEqual(env, {wc.TOKEN_ENV: EXPORTED})
        wc.remove_ambient_token(self.operator(), env)
        self.assertEqual(env, {})

    def test_a_provider_without_claude_reads_no_credential(self):
        self.assertEqual(wc.llm_env({"operator": {"enabled": True}}, ["codex"], {}), {})
        self.assertEqual(wc.llm_env(self.operator(), ["codex", "claude"], {}), {wc.TOKEN_ENV: SECRET})


class DeliveryTests(Base):
    def test_probe_receives_the_credential_in_its_launcher_only(self):
        seen = {}

        def probe(root, config, launcher):
            with mock.patch("independent_review_runner.subprocess_launcher") as launch:
                launcher(["claude"], root, 1)
            seen["env"] = launch.call_args.kwargs["env"]
            return {"ready": True}

        with mock.patch.object(workers, "read_platform_config", return_value=self.operator()), \
                mock.patch("independent_review_runner.settings", return_value={}), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(wc.TOKEN_ENV, None)
            readiness = workers.provider_readiness(ROOT, ["claude"], workdir=self.tmp, probe=probe)
            self.assertNotIn(wc.TOKEN_ENV, os.environ)
        self.assertEqual(readiness, {"claude": None})
        self.assertEqual(seen["env"][wc.TOKEN_ENV], SECRET)

    def test_unusable_credential_is_a_named_limitation_and_no_probe_runs(self):
        probe = mock.Mock()
        with mock.patch.object(workers, "read_platform_config", return_value=self.operator(content=None)), \
                mock.patch("independent_review_runner.settings", return_value={}):
            readiness = workers.provider_readiness(ROOT, ["claude"], workdir=self.tmp, probe=probe)
        self.assertIn("not readable", readiness["claude"])
        probe.assert_not_called()

    def test_project_checks_never_inherit_the_token(self):
        clean = common.credential_free_check_env({wc.TOKEN_ENV: EXPORTED, "PATH": "/bin"}, self.tmp)
        self.assertNotIn(wc.TOKEN_ENV, clean)

    def test_harness_push_environment_drops_the_token(self):
        env = workers.harness_push_env(self.repo(), {wc.TOKEN_ENV: EXPORTED, "PATH": os.environ["PATH"]})
        self.assertNotIn(wc.TOKEN_ENV, env)

    def repo(self) -> Path:
        path = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", "file:///unused"], check=True)
        return path

    def test_plain_writer_gets_the_credential_through_run_llm(self):
        with mock.patch.object(workers, "read_platform_config", return_value=self.operator()), \
                mock.patch.object(workers, "run_llm") as run:
            launch = workers.plain_writer_launch(ROOT, "claude")
            launch(["claude"], self.tmp, tmp=self.tmp, env=None, runner=mock.Mock(), home=self.tmp)
        self.assertEqual(run.call_args.kwargs["extra_env"], {wc.TOKEN_ENV: SECRET})

    def test_plain_codex_writer_gets_no_claude_credential(self):
        with mock.patch.object(workers, "read_platform_config", return_value={"operator": {"enabled": True}}), \
                mock.patch.object(workers, "run_llm") as run:
            workers.plain_writer_launch(ROOT, "codex")(["codex"], self.tmp, tmp=self.tmp, env=None,
                                                       runner=mock.Mock(), home=self.tmp)
        self.assertEqual(run.call_args.kwargs["extra_env"], {})

    def test_review_launch_failure_names_the_setting(self):
        checkout = self.tmp / "checkout"
        checkout.mkdir()
        job = {"task_identity": {"change": "c", "kind": "managed"}, "head": "a" * 40}
        with mock.patch("_platform_common.read_platform_config", return_value=self.operator(content=None)), \
                mock.patch("independent_review.resolve_change", return_value=checkout), \
                mock.patch.object(gate, "refresh_identity", return_value=job["task_identity"]):
            with self.assertRaisesRegex(workers.WorkerError, "not readable"):
                gate.execute_review(checkout, job, source_repo="s", branch="b", current_head=lambda: "x",
                                    runner=mock.Mock(), trusted_root=ROOT, review_config={"providers": ["claude"]})


class WorkerStartTests(Base):
    def test_the_committed_public_contract_is_the_hosted_placement(self):
        import tomllib

        contract = tomllib.loads((ROOT / "dev-platform" / "source-contract.toml").read_text())
        self.assertFalse(wc.operator_placement(contract))

    def test_work_next_removes_an_exported_token_on_the_operator_node(self):
        with mock.patch.dict(os.environ, {wc.TOKEN_ENV: EXPORTED}), \
                mock.patch.object(workers, "read_platform_config", return_value=self.operator()), \
                mock.patch.object(workers, "work_next", return_value={"status": "idle", "job": None}), \
                mock.patch.object(workers, "_coordinator_trust", return_value={}), \
                mock.patch("sys.stdout"):
            self.assertEqual(workers.main(["work-next", "--kinds", "review", "--repo", "o/r", "--dry-run"]), 0)
            self.assertNotIn(wc.TOKEN_ENV, os.environ)

    def test_credential_error_exits_naming_it(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(workers, "read_platform_config", return_value=self.operator(content=None)), \
                mock.patch("sys.stderr") as err:
            code = workers.main(["work-next", "--kinds", "repair", "--repo", "o/r", "--provider", "claude",
                                 "--repair-provider", "claude", "--llm-command", "claude -p", "--allow", "x", "--run"])
        self.assertEqual(code, 2)
        self.assertIn("not readable", "".join(call.args[0] for call in err.write.call_args_list))


if __name__ == "__main__":
    unittest.main()
