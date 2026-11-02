"""Requirement contribution and composition boundaries, including resumable Git facts."""
from __future__ import annotations

import collections
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import isolate_machine_pool_environment  # noqa: E402
from _platform_config import platform_config_text  # noqa: E402
import requirement_contributions as contributions
import requirement_composition as composition
import execute_requirement as execution
import pr_review_gate as review_gate
import candidate_lifecycle as lifecycle
import lifecycle_workers as workers
import requirement_integration as integration
from task_content_identity import review_content_identity

REQUIREMENT = "acme/backlog#7"


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, stdin=subprocess.DEVNULL,
                          text=True, capture_output=True, check=True).stdout.strip()


def setUpModule() -> None:
    # Full-check scenarios mock subprocess.run; an enabled machine pool would otherwise
    # acquire through that mock and see the operator's environment.
    isolate_machine_pool_environment()
    # Local-log scenarios: durable coordinator evidence (GitHub) is covered by the
    # coordinator-operations tests, so these scenarios never reach GitHub.
    for module in {sys.modules["agent_friction"]}:
        patcher = mock.patch.object(module, "read_durable_events", return_value=[])
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


PROJECT_CONTRACT = platform_config_text()


class Repository:
    def __init__(self, root, *, committed_contract=True):
        self.root = root
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "Test")
        git(root, "config", "user.email", "test@example.test")
        (root / "AGENTS.md").write_text("Bounded test repository\n")
        (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)  # committed project contract
        (root / "dev-platform").mkdir()
        (root / "dev-platform/checks.toml").write_text("# no generated files\n")
        if not committed_contract:
            # A source-repository history from before its public contract was committed:
            # the composition checkout only carries an installed, locally excluded contract.
            with (root / ".git" / "info" / "exclude").open("a") as handle:
                handle.write(".dev-platform.toml\n")
        self.base = self.commit("base")
        git(root, "update-ref", "refs/remotes/origin/main", self.base)
        self.manifest = contributions.seal({"version": 2, "requirement": REQUIREMENT,
            "repository": "acme/project", "work_identity": "BR-7", "base": self.base,
            "integration_branch": "requirement/BR-7", "expected_changes": ["first", "second"],
            "dependencies": {"first": [], "second": []}, "children": []})
        git(root, "switch", "-c", "requirement/BR-7")
        contributions.write_manifest(root, self.manifest)
        self.boundary = git(root, "rev-parse", "HEAD")

    def commit(self, message):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def child(self, name, number, tasks="- [x] Implement child\n"):
        git(self.root, "switch", "-c", f"agent/{name}", self.boundary)
        change = self.root / "openspec/changes" / name
        change.mkdir(parents=True)
        (change / "tasks.md").write_text(tasks)
        (change / "proposal.md").write_text(f"Implement {name}\n")
        (change / "automated-checks.json").write_text("{}\n")
        (change / "verification.md").write_text("Actual fixture evidence\n")
        (change / "independent-review-request.json").write_text("{}\n")
        (change / "independent-reviews").mkdir()
        (change / "independent-reviews/spec-fidelity.json").write_bytes(b'{"reviewed": true}\r\n')
        (self.root / f"{name}.txt").write_text(f"{name}\n")
        head = self.commit(name)
        identity = {"kind": "contribution", "change": name, "requirement": REQUIREMENT,
            "source_issue": f"acme/backlog#{number}", "target_branch": "requirement/BR-7",
            "contribution_base": self.boundary, "task_content": review_content_identity(self.root, name, self.boundary)}
        gates = {g: {"result": "passed", "identity": identity, "evidence": {"reviewed": True}}
                 for g in ("review", "selected-checks", "semantic-verification", "required-checks")}
        gates["required-checks"]["evidence"] = {"head": head, "kind": "passed"}
        for gate, filename in (("selected-checks", "automated-checks.json"), ("semantic-verification", "verification.md")):
            gates[gate]["evidence"] = review_gate.file_reference(self.root, change / filename)
        return {"number": number, "head": head, "task_identity": identity, "gates": gates}

    def integrate(self, candidate):
        git(self.root, "switch", "requirement/BR-7")
        git(self.root, "merge", "--no-ff", candidate["head"], "-m", "integrate child")
        merge = git(self.root, "rev-parse", "HEAD")
        pr = {"number": candidate["number"], "merged": True, "merge_commit_sha": merge,
              "head": {"sha": candidate["head"], "ref": f"agent/{candidate['task_identity']['change']}"},
              "base": {"ref": "requirement/BR-7"}}
        self.manifest = contributions.recover_contribution_merge(self.root, self.manifest, pr, candidate)
        contributions.write_manifest(self.root, self.manifest)
        return pr


class ContributionTests(unittest.TestCase):
    def test_hosted_manifest_push_auth_is_process_scoped_and_never_logged(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            origin = "https://github.com/acme/project.git"
            token = "secret-coordinator-token"
            git(fixture.root, "remote", "add", "origin", origin)
            before = (fixture.root / ".git/config").read_bytes()
            runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
            path = {"PATH": os.environ["PATH"]}
            with mock.patch.dict("os.environ", {"GH_TOKEN": token, **path}, clear=True), mock.patch.object(
                workers, "harness_git", side_effect=["", origin]
            ), mock.patch.object(workers, "active_gh_token", side_effect=lambda _c, env: env["GH_TOKEN"]):
                contributions.push_fast_forward(fixture.root, "requirement/BR-7", "", fixture.boundary, runner=runner)
            argv, kwargs = runner.call_args.args[0], runner.call_args.kwargs
            encoded = base64.b64encode(("x-access-token:" + token).encode()).decode()
            self.assertNotIn(token, str(argv))
            self.assertEqual(kwargs["env"]["GIT_CONFIG_KEY_1"], f"http.{origin}.extraheader")
            self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_1"], "AUTHORIZATION: basic " + encoded)
            self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
            clean = workers.credential_free_env(kwargs["env"])
            self.assertFalse(any(k in {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0",
                                      "GIT_CONFIG_KEY_1", "GIT_CONFIG_VALUE_1"} for k in clean))
            self.assertNotIn("GH_TOKEN", workers.credential_free_env(kwargs["env"]))
            self.assertEqual((fixture.root / ".git/config").read_bytes(), before)
            with mock.patch.object(workers, "harness_git", return_value=origin):
                with mock.patch.object(workers.subprocess, "run",
                                       return_value=subprocess.CompletedProcess([], 1, "", token)), \
                        self.assertRaisesRegex(workers.WorkerError, "authenticated gh credential") as missing:
                    workers.harness_push_env(fixture.root, {})
                self.assertNotIn(token, str(missing.exception))
            runner.return_value = subprocess.CompletedProcess([], 1, "", token + encoded)
            with mock.patch.dict("os.environ", {"GH_TOKEN": token, **path}, clear=True), mock.patch.object(
                workers, "harness_git", side_effect=["", origin]
            ), mock.patch.object(workers, "active_gh_token", side_effect=lambda _c, env: env["GH_TOKEN"]), \
                    self.assertRaises(contributions.ContributionError) as error:
                contributions.push_fast_forward(fixture.root, "requirement/BR-7", "", fixture.boundary, runner=runner)
            self.assertNotIn(token, str(error.exception))
            self.assertNotIn(encoded, str(error.exception))

    def test_repaired_contribution_requires_fresh_semantic_receipt(self):
        import post_review_finalization as finalization
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            child = fixture.child("first", 8)
            (fixture.root / "first.txt").write_text("repaired\n")
            head = fixture.commit("repair")
            identity = copy.deepcopy(child["task_identity"])
            identity["task_content"] = review_content_identity(fixture.root, "first", fixture.boundary)
            candidate = {"number": 8, "head": head, "task_identity": identity, "state": "finalize-pending",
                         "gates": {**child["gates"], "review": {"result": "passed", "identity": identity,
                                                                  "evidence": {"reviewed": True}}}}
            job = workers.build_job(candidate)
            adapter = SimpleNamespace(_transition=mock.Mock(), publish_job=mock.Mock(),
                _pr=lambda *a: {"head": {"sha": head}}, _comments=lambda *a: [], _derive=lambda *a: candidate)
            checks, archive = mock.Mock(return_value={"command": ["scripted"], "freshness": {
                "contract": "contribution-base", "base": identity["contribution_base"]}}), mock.Mock()
            receipt = fixture.root / "openspec/changes/first/verification.md"
            before = receipt.read_bytes()
            with tempfile.TemporaryDirectory() as workdir, mock.patch("openspec_lifecycle.verification_passed", return_value=True):
                outcome = finalization.run_claimed_finalize(fixture.root, "acme/project", candidate, job,
                    source_repo=str(fixture.root), branch="agent/first", current_head=lambda: head,
                    post_result=mock.Mock(), workdir=workdir, adapter=adapter, claim_current=lambda: True,
                    checks_runner=checks, archiver=archive, worker="w")
            self.assertEqual(outcome["status"], "blocked-retryable")
            self.assertIn("fresh semantic verification", outcome["reason"])
            self.assertEqual(adapter._transition.call_args.kwargs["red_gate"]["name"], "semantic-verification")
            self.assertEqual(receipt.read_bytes(), before)
            adapter.publish_job.assert_not_called()
            archive.assert_not_called()
            checks.assert_called_once()
            self.assertEqual(checks.call_args.kwargs, {"contribution_base": identity["contribution_base"]})

    def test_failed_contribution_checks_publish_discoverable_repair(self):
        import publication_queue as queue
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            candidate = fixture.child("first", 8)
            identity, head = candidate["task_identity"], candidate["head"]
            record = lifecycle.build_handoff_record(number=8, state="contribution-integration-pending", head=head,
                task_identity=identity, gates=candidate["gates"], red_gate=None, not_reverified=[], attempts={},
                next_job=workers.job_record("contribution-integration", head, identity, 1, target_head=fixture.boundary),
                at="2026-10-06T00:00:00Z", route={"provider": "codex", "profile": "standard", "change": "first"})
            comments = [{"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}]
            pr = {"number": 8, "state": "open", "head": {"sha": head, "ref": "agent/first"},
                  "labels": [], "base": {"ref": "requirement/BR-7"}}
            checks = {"head": head, "kind": "failed", "detail": "unit failed"}
            def post(root, *args, **kwargs):
                comments.append({"id": len(comments) + 1, "author_association": "OWNER", "body": kwargs["data"]["body"]})
            with mock.patch.object(queue, "_repo", return_value="acme/project"), \
                 mock.patch.object(queue, "_queued", return_value=[(1, 8, {})]), \
                 mock.patch.object(queue, "_pr", return_value=pr), \
                 mock.patch.object(queue, "_comments", side_effect=lambda *a: comments), \
                 mock.patch.object(queue, "candidate_status", side_effect=lambda *a, **kw: lifecycle.derive_candidate(pr, comments, checks)), \
                 mock.patch.object(queue, "trusted_apps", return_value=frozenset()), \
                 mock.patch.object(queue, "trusted_writers", return_value=frozenset()), \
                 mock.patch.object(queue, "_gh", side_effect=post), \
                 mock.patch.object(queue, "_project_lifecycle_label"), mock.patch.object(queue, "emit_friction"), \
                 mock.patch("independent_review_runner.settings", return_value={"providers": ["codex"]}):
                result = queue.worker(fixture.root)
                published = len(comments)
                queue.worker(fixture.root)
                self.assertEqual(len(comments), published)
            self.assertEqual(result["state"], "repair-pending")
            discovered = lifecycle.derive_candidate(pr, comments)
            self.assertEqual(workers.build_job(discovered)["kind"], "repair")
            self.assertEqual(discovered["gates"]["required-checks"]["result"], "failed")
            self.assertEqual(discovered["red_gate"]["name"], "required-checks")
            self.assertEqual(review_gate.repair_brief(discovered)["findings"][0]["id"], "required-checks-failed")

    def test_composition_full_checks_use_the_project_check_environment(self):
        import os
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root, operator = Path(tmp), Path(outside)
            (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
            (operator / "home" / ".cache" / "uv").mkdir(parents=True)
            (operator / "home" / ".cache" / "uv" / "marker").write_text("cache")
            (operator / "bin").mkdir()
            tool = operator / "bin" / "uv"
            tool.write_text("#!/bin/sh\n")
            tool.chmod(0o755)
            (root / "dev-platform").mkdir()
            (root / "dev-platform" / "checks.toml").write_text(
                '[runtime]\nrequired_tools = ["uv"]\nrequired_env = ["APP_DB"]\nhome_paths = [".cache/uv"]\n')
            grant = operator / "grant.toml"
            grant.write_text('allow_home_paths = [".cache/uv"]\n')
            observed = []
            def command(*args, **kwargs):
                env = kwargs["env"]
                home = Path(env["HOME"])
                observed.append((env, (home / ".cache" / "uv" / "marker").read_text()))
                self.assertNotEqual(env["HOME"], str(operator / "home"))
                for key in ("GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "GIT_CONFIG_COUNT"):
                    self.assertNotIn(key, env)
                self.assertEqual(env["APP_DB"], "postgres://x")
                self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
                return SimpleNamespace(returncode=0)
            environ = {"HOME": str(operator / "home"), "PATH": f"{operator / 'bin'}:/usr/bin", "GH_TOKEN": "secret",
                       "GITHUB_TOKEN": "secret", "SSH_AUTH_SOCK": "/agent", "APP_DB": "postgres://x",
                       "DEV_PLATFORM_PROJECT_RUNTIME_FILE": str(grant)}
            with mock.patch.dict(os.environ, environ, clear=True), \
                 mock.patch.object(integration, "_full_check_commands", return_value=["candidate-check"]), \
                 mock.patch.object(integration.subprocess, "run", side_effect=command):
                integration._run_full_checks(root)
            self.assertEqual(len(observed), 1)
            self.assertEqual(observed[0][1], "cache")
            self.assertFalse(Path(observed[0][0]["HOME"]).exists())

    def test_composition_full_checks_without_runtime_use_credential_free_isolated_home(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
            observed = []
            def command(*args, **kwargs):
                env = kwargs["env"]
                observed.append(env)
                self.assertTrue(Path(env["HOME"]).is_dir())
                self.assertEqual(list(Path(env["HOME"]).iterdir()), [])
                self.assertNotEqual(env["HOME"], "/operator-home")
                for key in ("GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK"):
                    self.assertNotIn(key, env)
                self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
                return SimpleNamespace(returncode=0)
            import site
            with mock.patch.dict(os.environ, {"HOME": "/operator-home", "GH_TOKEN": "secret",
                    "GITHUB_TOKEN": "secret", "SSH_AUTH_SOCK": "/agent"}), \
                 mock.patch.object(site, "getuserbase", return_value="/operator-home/Library/Python/3.13"), \
                 mock.patch.object(integration, "_full_check_commands", return_value=["candidate-check"]), \
                 mock.patch.object(integration.subprocess, "run", side_effect=command):
                integration._run_full_checks(root)
            self.assertEqual(len(observed), 1)
            self.assertFalse(Path(observed[0]["HOME"]).exists())
            # User-installed check tooling (copier, ruff) stays importable from the operator's user base.
            self.assertEqual(observed[0]["PYTHONUSERBASE"], "/operator-home/Library/Python/3.13")

    def platform_layout(self, root, registry_source):
        (root / "template" / "scripts").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "scripts" / "managed_projects.py").write_text("")
        trusted = root / "trusted"
        (trusted / "scripts").mkdir(parents=True)
        (trusted / "scripts" / "managed_projects.py").write_text(registry_source)
        return trusted

    def test_composition_full_checks_validate_the_trusted_registry_without_showing_it(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
            trusted = self.platform_layout(root, "from pathlib import Path\n"
                                           "def configured_registry(*, root):\n    return Path(root) / 'op dir' / 'registry.toml'\n")
            secret = str(trusted / "op dir" / "registry.toml")
            commands = integration._full_check_commands(root, trusted)
            self.assertIn(f"python3 scripts/managed_projects.py --registry '{secret}' validate", commands)
            self.assertEqual(integration._full_check_commands(root), list(integration.PLATFORM_FULL_CHECK_COMMANDS))
            ran = []
            def command(cmd, **kwargs):
                ran.append(cmd)
                return SimpleNamespace(returncode=2 if "managed_projects.py" in cmd else 0)
            out = io.StringIO()
            with mock.patch.object(integration.subprocess, "run", side_effect=command), contextlib.redirect_stdout(out):
                with self.assertRaises(integration.RequirementIntegrationError) as raised:
                    integration._run_full_checks(root, trusted_root=trusted)
            self.assertTrue(any(secret in cmd for cmd in ran))
            self.assertNotIn(secret, str(raised.exception))
            self.assertNotIn(secret, out.getvalue())
            self.assertIn("--registry <operator>", str(raised.exception))
            self.assertIn("--registry <operator>", out.getvalue())

    def test_unconfigured_trusted_registry_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trusted = self.platform_layout(root, "def configured_registry(*, root):\n    raise ValueError('operator configuration is not enabled')\n")
            with self.assertRaisesRegex(integration.RequirementIntegrationError, "trusted managed project registry is unavailable"):
                integration._full_check_commands(root, trusted)
            (trusted / "scripts" / "managed_projects.py").unlink()
            with self.assertRaisesRegex(integration.RequirementIntegrationError, "no managed project registry tooling"):
                integration._full_check_commands(root, trusted)

    def test_interrupted_merge_append_is_idempotent_and_preserves_ancestry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            first, second = fixture.child("first", 8), fixture.child("second", 9)
            pr = fixture.integrate(first)
            original = copy.deepcopy(fixture.manifest)
            recovered = contributions.recover_contribution_merge(fixture.root, original, pr, first)
            self.assertEqual(recovered, original)
            fixture.integrate(second)
            contributions.validate(fixture.manifest, original)
            self.assertEqual(fixture.manifest["children"][:1], original["children"])
            self.assertTrue(integration.manifest_complete(fixture.manifest))
            for child in (first, second):
                git(fixture.root, "merge-base", "--is-ancestor", child["head"], "HEAD")
            composition.validate_children(fixture.root, fixture.manifest)

    def test_children_reviewed_before_a_committed_contract_use_the_composition_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp), committed_contract=False)
            first, second = fixture.child("first", 8), fixture.child("second", 9)
            fixture.integrate(first)
            fixture.integrate(second)
            for child in (first, second):
                self.assertNotIn(".dev-platform.toml", git(fixture.root, "ls-tree", "--name-only", child["head"]).split())
            composition.validate_children(fixture.root, fixture.manifest)

    def test_composition_without_a_contract_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp), committed_contract=False)
            first, second = fixture.child("first", 8), fixture.child("second", 9)
            fixture.integrate(first)
            fixture.integrate(second)
            (fixture.root / ".dev-platform.toml").unlink()
            with self.assertRaisesRegex(workers.WorkerError, "trusted platform contract .* is missing"):
                composition.validate_children(fixture.root, fixture.manifest)

    def test_changed_removed_reordered_child_and_graph_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            fixture.integrate(fixture.child("first", 8))
            fixture.integrate(fixture.child("second", 9))
            for mutation in (lambda m: m["children"].reverse(), lambda m: m["children"].pop(),
                             lambda m: m["children"][0].update(head="f" * 40),
                             lambda m: m["dependencies"].update(second=["first"])):
                value = copy.deepcopy(fixture.manifest)
                mutation(value)
                with self.subTest(value=value), self.assertRaises(contributions.ContributionError):
                    contributions.validate(contributions.seal(value), fixture.manifest)

    def test_unknown_cycle_and_dependency_before_predecessor_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            for graph in ({"first": ["missing"], "second": []}, {"first": ["second"], "second": ["first"]}):
                with self.assertRaises(contributions.ContributionError):
                    contributions.validate(contributions.seal({**fixture.manifest, "dependencies": graph}))
            candidate = fixture.child("second", 9)
            fixture.manifest = contributions.seal({**fixture.manifest, "dependencies": {"first": [], "second": ["first"]}})
            with self.assertRaises(contributions.ContributionError):
                fixture.integrate(candidate)

    def test_required_checks_must_name_exact_head_and_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            candidate = fixture.child("first", 8)
            contributions.require_gates(candidate)
            for key, value in (("evidence", {"head": "f" * 40}), ("identity", {})):
                stale = copy.deepcopy(candidate)
                stale["gates"]["required-checks"][key] = value
                with self.assertRaises(contributions.ContributionError):
                    contributions.require_gates(stale)

    def test_non_fast_forward_or_concurrent_push_is_refused_before_push(self):
        runner = mock.Mock()
        with mock.patch.object(workers, "harness_git", return_value="b" * 40 + " refs/heads/requirement/BR-7"):
            with self.assertRaises(contributions.ContributionError):
                contributions.push_fast_forward(Path("/unused"), "requirement/BR-7", "a" * 40, "c" * 40, runner=runner)
        runner.assert_not_called()
        with mock.patch.object(workers, "harness_git", side_effect=["a" * 40 + " ref", workers.WorkerError("divergent")]):
            with self.assertRaises(workers.WorkerError):
                contributions.push_fast_forward(Path("/unused"), "requirement/BR-7", "a" * 40, "c" * 40, runner=runner)
        runner.assert_not_called()

    def test_branch_creation_rerun_reuses_owned_committed_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, seed = root / "remote.git", root / "seed"
            remote.mkdir(); seed.mkdir()
            git(remote, "init", "--bare", "-b", "main")
            git(seed, "init", "-b", "main")
            git(seed, "config", "user.name", "Test"); git(seed, "config", "user.email", "test@example.test")
            (seed / "AGENTS.md").write_text("test\n")
            (seed / ".dev-platform.toml").write_text(PROJECT_CONTRACT)  # committed project contract
            (seed / "dev-platform").mkdir()
            (seed / "dev-platform/checks.toml").write_text("# no generated files\n")
            git(seed, "add", "."); git(seed, "commit", "-m", "base")
            git(seed, "remote", "add", "origin", str(remote)); git(seed, "push", "origin", "main")
            kwargs = {"requirement": REQUIREMENT, "repository": "acme/project", "expected_changes": ["first", "second"],
                      "dependencies": {"first": [], "second": []}, "source_repo": remote.as_uri()}
            first = contributions.ensure_integration_branch(seed, **kwargs)
            second = contributions.ensure_integration_branch(seed, **kwargs)
            self.assertEqual(first, second)
            with self.assertRaises(contributions.ContributionError):
                contributions.ensure_integration_branch(seed, **{**kwargs, "expected_changes": ["second", "first"]})

    def test_integrated_contribution_has_no_terminal_job(self):
        candidate = {"task_identity": {"kind": "contribution"}, "state": "contribution-integrated", "next_job": None}
        self.assertIsNone(workers.build_job(candidate))
        self.assertIn("contribution-integrated", lifecycle.STATES)

    def test_merge_before_manifest_and_manifest_before_marker_resume_without_remerge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed"; seed.mkdir()
            fixture = Repository(seed)
            candidate = fixture.child("first", 8)
            git(seed, "switch", "requirement/BR-7")
            git(seed, "merge", "--no-ff", candidate["head"], "-m", "GitHub merge")
            pr = {"number": 8, "merged": True, "merge_commit_sha": git(seed, "rev-parse", "HEAD"),
                  "head": {"sha": candidate["head"], "ref": "agent/first"}, "base": {"ref": "requirement/BR-7"}}
            remote = root / "remote.git"
            git(root, "clone", "--bare", str(seed), str(remote))
            adapter = SimpleNamespace(_pr=lambda *args: pr, _gh=mock.Mock(),
                                      _transition=mock.Mock(side_effect=RuntimeError("interrupted after manifest push")))
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                contributions.merge_reviewed_contribution(seed, "acme/project", candidate,
                    adapter=adapter, source_repo=remote.as_uri())
            head = git(remote, "rev-parse", "requirement/BR-7")
            adapter._transition.side_effect = None
            outcome = contributions.merge_reviewed_contribution(seed, "acme/project", candidate,
                adapter=adapter, source_repo=remote.as_uri())
            self.assertEqual(outcome["state"], "contribution-integrated")
            self.assertEqual(head, git(remote, "rev-parse", "requirement/BR-7"))
            adapter._gh.assert_not_called()
            path = integration._candidate_manifest_path(REQUIREMENT)
            manifest = json.loads(git(remote, "show", f"{head}:{path}"))
            self.assertEqual(len(manifest["children"]), 1)

    def test_private_manifest_uses_only_public_handles_and_proves_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            value = contributions.seal({**fixture.manifest, "requirement": "pln_" + "a" * 32})
            contributions.validate(value)
            import private_lineage
            with mock.patch("_platform_common.read_platform_config", return_value={"development_backlog": {"repository": "acme/backlog"}}), mock.patch.object(
                private_lineage, "require_handle"
            ) as prove:
                self.assertEqual(contributions.private_requirement(fixture.root, value), REQUIREMENT)
            prove.assert_called_once_with(fixture.root, REQUIREMENT, "requirement-integration", value["requirement"])
            self.assertNotIn("acme/backlog", json.dumps(value))

    def _moved_target_fixture(self, root):
        """A reviewed contribution bound to the boundary head, an unmerged PR and a bare remote."""
        seed = root / "seed"; seed.mkdir()
        fixture = Repository(seed)
        candidate = fixture.child("first", 8)
        remote = root / "remote.git"
        git(root, "clone", "--bare", str(seed), str(remote))
        git(remote, "update-ref", "refs/pull/8/head", candidate["head"])
        pr = {"number": 8, "merged": False, "head": {"sha": candidate["head"], "ref": "agent/first"},
              "base": {"ref": "requirement/BR-7"}}
        adapter = SimpleNamespace(_pr=mock.Mock(return_value=pr), _gh=mock.Mock(), _transition=mock.Mock(),
                                  candidate_status=mock.Mock(return_value=candidate), publish_job=mock.Mock(),
                                  merge_conflicts=mock.Mock(return_value=[]), _integration_repair=mock.Mock())
        return fixture, candidate, remote, pr, adapter

    def _advance_remote(self, fixture, remote, name, *, base=None):
        """Move requirement/BR-7 on the remote: on top of the boundary, or rewritten from ``base``."""
        git(fixture.root, "switch", "-C", f"move-{name}", base or "requirement/BR-7")
        if base is not None:
            # A distinct first commit, so the rewritten manifest commit can never equal the boundary.
            (fixture.root / "rewrite.txt").write_text(f"{name}\n")
            fixture.commit("rewrite")
            contributions.write_manifest(fixture.root, fixture.manifest)
        (fixture.root / f"{name}.txt").write_text(f"{name}\n")
        head = fixture.commit(name)
        git(fixture.root, "push", "--force", str(remote), f"{head}:refs/heads/requirement/BR-7")
        return head

    def test_moved_target_reoffers_the_job_on_the_new_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, candidate, remote, _, adapter = self._moved_target_fixture(Path(tmp))
            moved = self._advance_remote(fixture, remote, "other")
            outcome = contributions.merge_reviewed_contribution(
                fixture.root, "acme/project", candidate, adapter=adapter, source_repo=remote.as_uri(),
                expected_target_head=fixture.boundary)
            self.assertEqual(outcome, {"state": "target-moved", "number": 8, "target_head": moved})
            adapter.publish_job.assert_called_once_with(
                fixture.root, "acme/project", 8, "contribution-integration", candidate["head"],
                task_identity=candidate["task_identity"], target_head=moved)
            adapter._gh.assert_not_called()
            adapter._transition.assert_not_called()
            self.assertEqual(git(remote, "rev-parse", "requirement/BR-7"), moved)

    def test_target_moving_during_the_run_reoffers_on_the_observed_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, candidate, remote, _, adapter = self._moved_target_fixture(Path(tmp))
            moved = []
            def conflicts(*_args):
                moved.append(self._advance_remote(fixture, remote, "racing"))
                return []
            adapter.merge_conflicts.side_effect = conflicts
            outcome = contributions.merge_reviewed_contribution(
                fixture.root, "acme/project", candidate, adapter=adapter, source_repo=remote.as_uri(),
                expected_target_head=fixture.boundary)
            self.assertEqual(outcome["state"], "target-moved")
            self.assertEqual(adapter.publish_job.call_args.kwargs["target_head"], moved[0])
            adapter._gh.assert_not_called()

    def test_moved_target_without_the_contribution_base_fails_without_reoffer(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, candidate, remote, _, adapter = self._moved_target_fixture(Path(tmp))
            rewritten = self._advance_remote(fixture, remote, "rewritten", base=fixture.base)
            with self.assertRaisesRegex(contributions.ContributionError, f"{rewritten} no longer contains contribution base"):
                contributions.merge_reviewed_contribution(
                    fixture.root, "acme/project", candidate, adapter=adapter, source_repo=remote.as_uri(),
                    expected_target_head=fixture.boundary)
            adapter.publish_job.assert_not_called()
            adapter._gh.assert_not_called()

    def test_moved_target_with_a_lost_claim_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, candidate, remote, _, adapter = self._moved_target_fixture(Path(tmp))
            self._advance_remote(fixture, remote, "other")
            outcome = contributions.merge_reviewed_contribution(
                fixture.root, "acme/project", candidate, adapter=adapter, source_repo=remote.as_uri(),
                expected_target_head=fixture.boundary, claim_current=mock.Mock(side_effect=[True, False]))
            self.assertEqual(outcome, {"state": "discarded"})
            adapter.publish_job.assert_not_called()

    def test_matching_target_head_merges_without_reoffer(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, candidate, remote, pr, adapter = self._moved_target_fixture(Path(tmp))
            def protected_merge(*_args, **_kwargs):
                git(fixture.root, "switch", "requirement/BR-7")
                git(fixture.root, "merge", "--no-ff", candidate["head"], "-m", "GitHub merge")
                merge = git(fixture.root, "rev-parse", "HEAD")
                git(fixture.root, "push", str(remote), "requirement/BR-7")
                pr.update({"merged": True, "merge_commit_sha": merge})
                return {"merged": True}
            adapter._gh.side_effect = protected_merge
            outcome = contributions.merge_reviewed_contribution(
                fixture.root, "acme/project", candidate, adapter=adapter, source_repo=remote.as_uri(),
                expected_target_head=fixture.boundary)
            self.assertEqual(outcome["state"], "contribution-integrated")
            adapter.publish_job.assert_not_called()
            adapter._gh.assert_called_once()

    def test_lost_claim_refuses_merge_before_network_or_checkout(self):
        candidate = {"number": 1, "head": "a" * 40, "task_identity": {}, "gates": {}}
        with mock.patch.object(contributions, "require_gates"), mock.patch.object(workers, "prepare_checkout") as checkout:
            result = contributions.merge_reviewed_contribution(Path("/unused"), "acme/project", candidate, claim_current=lambda: False)
        self.assertEqual(result["state"], "discarded")
        checkout.assert_not_called()

    def test_private_child_ordinal_resolves_linked_issue_not_issue_number(self):
        manifest = {"requirement": REQUIREMENT, "work_identity": "BR-7", "children": [
            {"change": "first", "work_identity": "BR-7/T2", "source_issue": "pln_" + "b" * 32}]}
        parent = {"body": "<!-- requirement-children:start -->\n- [ ] acme/backlog#373\n<!-- requirement-children:end -->\n"
                         "<!-- br-child:acme/backlog#373:2 -->\n"}
        child = {"body": f"Requirement: {REQUIREMENT}\nWork identity: BR-7/T2\n"}
        fetch = mock.Mock(side_effect=[parent, child])
        prove = mock.Mock()
        result = contributions.private_manifest(Path("/unused"), manifest, fetch_issue=fetch, prove_handle=prove)
        self.assertEqual(result["children"][0]["source_issue"], "acme/backlog#373")
        prove.assert_called_once_with(Path("/unused"), "acme/backlog#373", "first", "pln_" + "b" * 32)
        with self.assertRaisesRegex(contributions.ContributionError, "exact linked"):
            contributions.private_manifest(Path("/unused"), manifest,
                fetch_issue=mock.Mock(side_effect=[{"body": "<!-- br-child:acme/backlog#373:2 -->"}]), prove_handle=prove)


class CompositionTests(unittest.TestCase):
    def fixture(self, root):
        fixture = Repository(root)
        first, second = fixture.child("first", 8), fixture.child("second", 9)
        fixture.integrate(first); fixture.integrate(second)
        return fixture

    def test_composition_offer_binds_child_route_providers_without_current_route(self):
        import model_routing
        import independent_review_runner as reviewer
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            adapter = SimpleNamespace(github_cli_env=lambda root: {},
                find_exact_head_pr=lambda *a: SimpleNamespace(available=True, stale_open=None),
                ensure_pr=lambda *a, **kw: SimpleNamespace(number=11, url="pr", already_merged=False),
                _pr=lambda *a: {}, _comments=lambda *a: [], _derive=lambda *a: {},
                _transition=mock.Mock(return_value={}), publish_job=mock.Mock())
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                original_checkout(source, temporary, name, ref, **options) if "composition-child-" in temporary else fixture.root), mock.patch.object(
                reviewer, "settings", return_value={}
            ), mock.patch.object(model_routing, "read_durable_route", side_effect=[
                (SimpleNamespace(provider="codex"), None), (SimpleNamespace(provider="claude"), None)
            ]) as routes, mock.patch.object(model_routing, "read_current_durable_route", side_effect=AssertionError("integration route")):
                composition.publish_composition(fixture.root, "acme/project", fixture.manifest, head, adapter=adapter)
            self.assertEqual(adapter.publish_job.call_args.kwargs["providers"], ["codex", "claude"])
            self.assertEqual([c.args[1:] for c in routes.call_args_list], [("acme/backlog#8", "first"), ("acme/backlog#9", "second")])
            with mock.patch.object(reviewer, "settings", return_value={"providers": ["invalid"]}):
                with self.assertRaisesRegex(contributions.ContributionError, "explicit valid"):
                    composition.composition_providers(fixture.root, fixture.manifest)

    def test_parent_postmerge_jobs_process_every_child_and_retry_refused_cleanup(self):
        import integration_contour as contour
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            ops, post = mock.Mock(), mock.Mock()
            ops.lineage.return_value = None
            ops.cleanup.return_value = {"removed": [], "errors": []}
            for kind in ("retrospective", "cleanup"):
                job = {"number": 11, **workers.job_record(kind, head, identity, 0)}
                candidate = {"number": 11, "head": head, "state": "merged", "task_identity": identity, "next_job": job}
                with mock.patch.object(workers, "prepare_checkout", return_value=fixture.root), mock.patch(
                    "agent_friction.ambiguous_attribution_events", return_value=[]
                ), mock.patch.object(contour, "_events_for", return_value=[]), mock.patch(
                    "agent_friction.record_checkpoint"
                ) as checkpoint:
                    result = contour.run_claimed_post_merge(fixture.root, "acme/project", candidate, job,
                        branch="requirement/BR-7", post_result=post, ops=ops, claim_current=lambda: True, worker="w")
                    self.assertEqual(result["status"], "done")
                    if kind == "retrospective":
                        self.assertEqual([(c.args[0], c.kwargs["head"]) for c in checkpoint.call_args_list],
                            [(c["source_branch"], c["head"]) for c in fixture.manifest["children"]] + [("requirement/BR-7", head)])
                    else:
                        self.assertEqual([(c.args[1], c.args[2], c.args[3]) for c in ops.cleanup.call_args_list],
                            [(c["source_branch"], c["pr_number"], c["head"]) for c in fixture.manifest["children"]] + [("requirement/BR-7", 11, head)])
                        ops.cleanup.reset_mock()
                        ops.cleanup.side_effect = [{"errors": [{"error": "active-writer"}]}]
                        blocked = contour.run_claimed_post_merge(fixture.root, "acme/project", candidate, job,
                            branch="requirement/BR-7", post_result=post, ops=ops, claim_current=lambda: True, worker="w")
                        self.assertEqual(blocked["status"], "blocked")
                        self.assertEqual(ops.cleanup.call_count, 1)
                        ops.cleanup.side_effect = None
                        resumed = contour.run_claimed_post_merge(fixture.root, "acme/project", candidate, job,
                            branch="requirement/BR-7", post_result=post, ops=ops, claim_current=lambda: True, worker="w")
                        self.assertEqual(resumed["status"], "done")

    def test_three_child_composition_preserves_parallel_and_dependent_ancestry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            fixture.manifest = contributions.seal({**fixture.manifest,
                "expected_changes": ["first", "second", "third"],
                "dependencies": {"first": [], "second": [], "third": ["first", "second"]}})
            contributions.write_manifest(fixture.root, fixture.manifest)
            fixture.boundary = git(fixture.root, "rev-parse", "HEAD")
            first, second = fixture.child("first", 8), fixture.child("second", 9)
            self.assertEqual(first["task_identity"]["contribution_base"], second["task_identity"]["contribution_base"])
            fixture.integrate(first); fixture.integrate(second)
            fixture.boundary = git(fixture.root, "rev-parse", "HEAD")
            third = fixture.child("third", 373)
            for predecessor in (first, second):
                git(fixture.root, "merge-base", "--is-ancestor", predecessor["head"], third["head"])
            fixture.integrate(third)
            composition.validate_children(fixture.root, fixture.manifest)
            request = composition.prepare_request(fixture.root, fixture.manifest, "Deliver the complete Requirement")
            self.assertEqual([child["change"] for child in request["children"]], ["first", "second", "third"])
            for perspective in request["perspectives"].values():
                self.assertIn("Review only cross-child", perspective["objective"])

    def test_unchanged_children_receive_only_composition_objectives(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            request = composition.prepare_request(fixture.root, fixture.manifest, "Ship both capabilities")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            composition.validate_request(request, identity)
            for perspective in request["perspectives"].values():
                self.assertIn("Review only cross-child", perspective["objective"])
                self.assertIn("Do not fully re-review unchanged", perspective["objective"])
                self.assertIn("Ship both capabilities", perspective["objective"])
            self.assertEqual(len(request["children"]), 2)

    def test_reviewed_dependent_shared_edit_and_composition_repair_preserve_child_proofs(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            fixture.manifest = contributions.seal({**fixture.manifest, "dependencies": {"first": [], "second": ["first"]}})
            contributions.write_manifest(fixture.root, fixture.manifest)
            fixture.boundary = git(fixture.root, "rev-parse", "HEAD")
            first = fixture.child("first", 8)
            fixture.integrate(first)
            fixture.boundary = git(fixture.root, "rev-parse", "HEAD")
            second = fixture.child("second", 9)
            (fixture.root / "first.txt").write_text("first extended by second\n")
            second["head"] = fixture.commit("dependent shared edit")
            second["task_identity"]["task_content"] = review_content_identity(fixture.root, "second", fixture.boundary)
            second["gates"]["required-checks"]["evidence"]["head"] = second["head"]
            fixture.integrate(second)
            before = composition.composition_identity(fixture.root, fixture.manifest)
            (fixture.root / "first.txt").write_text("composition repair\n")
            fixture.commit("repair")
            after = composition.composition_identity(fixture.root, fixture.manifest)
            self.assertEqual(before["children"], after["children"])
            self.assertNotEqual(before["task_content"], after["task_content"])
            bad = copy.deepcopy(fixture.manifest)
            bad["children"][0]["task_identity"]["task_content"]["paths"]["first.txt"] = "f" * 40
            bad["children"][0]["reviewed_evidence_digest"] = integration._digest(bad["children"][0]["gates"])
            with self.assertRaises(contributions.ContributionError):
                composition.composition_identity(fixture.root, contributions.seal(bad))

    def test_changed_child_receipt_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            (fixture.root / "openspec/changes/first/verification.md").write_text("changed\n")
            fixture.commit("receipt drift")
            with self.assertRaises(contributions.ContributionError):
                composition.composition_identity(fixture.root, fixture.manifest)

    def test_incomplete_manifest_cannot_offer_composition_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            fixture.integrate(fixture.child("first", 8))
            with self.assertRaises(contributions.ContributionError):
                composition.composition_identity(fixture.root, fixture.manifest)

    def test_final_gates_require_archive_and_exact_checks_but_no_retrospective(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            # Archive is fixture bookkeeping; no actual platform archive command is run.
            for child in fixture.manifest["children"]:
                source = fixture.root / "openspec/changes" / child["change"]
                target = fixture.root / "openspec/changes/archive" / ("2026-10-06-" + child["change"])
                target.parent.mkdir(parents=True, exist_ok=True)
                source.rename(target)
            fixture.commit("archive all")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            head = git(fixture.root, "rev-parse", "HEAD")
            gates = {g: {"result": "passed", "identity": identity, "evidence": {"head": head}}
                     for g in ("review", "finalization", "full-checks", "required-checks")}
            gates["required-checks"]["evidence"]["kind"] = "passed"
            candidate = {"head": head, "task_identity": identity, "gates": gates}
            composition.require_final_gates(fixture.root, fixture.manifest, candidate, head, trusted_root=fixture.root)
            for name in gates:
                bad = copy.deepcopy(candidate); bad["gates"].pop(name)
                with self.subTest(gate=name), self.assertRaises(contributions.ContributionError):
                    composition.require_final_gates(fixture.root, fixture.manifest, bad, head, trusted_root=fixture.root)
            stale = copy.deepcopy(candidate); stale["gates"]["full-checks"]["evidence"]["head"] = "f" * 40
            with self.assertRaises(contributions.ContributionError):
                composition.require_final_gates(fixture.root, fixture.manifest, stale, head, trusted_root=fixture.root)

    def test_existing_exact_draft_rerun_reuses_pr_without_ready_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            lookup = SimpleNamespace(available=True, stale_open=None)
            adapter = SimpleNamespace(github_cli_env=lambda root: {}, find_exact_head_pr=mock.Mock(return_value=lookup),
                ensure_pr=mock.Mock(return_value=SimpleNamespace(number=11, url="https://example.test/pr/11", already_merged=False)))
            for _ in range(2):
                result = composition.publish_composition(fixture.root, "acme/project", fixture.manifest, fixture.boundary, adapter=adapter)
                self.assertEqual(result["status"], "draft-published")
            self.assertEqual(adapter.ensure_pr.call_count, 2)
            self.assertTrue(all(c.kwargs["draft"] for c in adapter.ensure_pr.call_args_list))
            self.assertEqual(adapter.find_exact_head_pr.call_args.args[2:4], ("requirement/BR-7", "main"))
            adapter.find_exact_head_pr.return_value.stale_open = {"head": "different"}
            with self.assertRaises(contributions.ContributionError):
                composition.publish_composition(fixture.root, "acme/project", fixture.manifest, fixture.boundary, adapter=adapter)
            self.assertEqual(adapter.ensure_pr.call_count, 2)

    def test_terminal_reconciliation_refuses_nonexact_merge_before_any_mutation(self):
        adapter = SimpleNamespace(_pr=lambda *args: {"merged": True, "head": {"sha": "f" * 40}, "base": {"ref": "main"}})
        with self.assertRaises(contributions.ContributionError):
            composition.reconcile_composition(Path("/unused"), "acme/project", {}, "a" * 40, 1, adapter=adapter)

    def test_terminal_gate_checkout_gets_the_trusted_integration_contract(self):
        head = "a" * 40
        pr = {"merged": True, "head": {"sha": head}, "base": {"ref": "main"}}
        adapter = SimpleNamespace(_pr=lambda *args: pr, _comments=lambda *args: [], _derive=lambda *args: {})
        stop = contributions.ContributionError("stop after the gate checkout")
        with mock.patch.object(composition.workers, "prepare_checkout", return_value=Path("/c")) as checkout, \
                mock.patch.object(composition, "require_final_gates", side_effect=stop):
            with self.assertRaises(contributions.ContributionError):
                composition.reconcile_composition(Path("/integration"), "acme/project", {}, head, 1, adapter=adapter)
        self.assertEqual(checkout.call_args.kwargs["contract_from"], Path("/integration/.dev-platform.toml"))

    def test_archived_contract_content_is_in_composition_review_diff(self):
        import independent_review_runner as reviewer
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            for name in fixture.manifest["expected_changes"]:
                target = fixture.root / "openspec/changes/archive" / ("2026-10-06-" + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                (fixture.root / "openspec/changes" / name).rename(target)
            fixture.commit("archive children")
            proposal = fixture.root / "openspec/changes/archive/2026-10-06-first/proposal.md"
            proposal.write_text("Repaired archived contract\n")
            fixture.commit("repair archived contract")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            paths = composition.review_diff_paths(fixture.root, fixture.manifest, identity)
            diff, error = reviewer.candidate_diff(fixture.root, fixture.manifest["base"], paths)
            self.assertIsNone(error)
            self.assertIn(str(proposal.relative_to(fixture.root)), diff)
            self.assertIn("Repaired archived contract", diff)
            self.assertFalse(any("verification.md" in p for p in paths))

    def unarchiveable_fixture(self, root):
        fixture = Repository(root)
        first, second = fixture.child("first", 8), fixture.child("second", 9, tasks="- [x] Done\n- [ ] Publish\n")
        fixture.integrate(first); fixture.integrate(second)
        return fixture

    def test_finalization_refuses_unarchiveable_child_before_archiving_any(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.unarchiveable_fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gates = {"review": {"result": "passed", "identity": identity, "evidence": {"reviewed": True}}}
            kwargs = {"source_repo": str(fixture.root), "branch": "requirement/BR-7", "current_head": lambda: head,
                      "archiver": lambda *a: self.fail("must not archive any child")}
            with mock.patch.object(composition, "validate_composition_reports"), \
                    self.assertRaisesRegex(workers.WorkerError, r"second: 1 of 2 task\(s\) remain incomplete"):
                composition.execute_composition_finalize(fixture.root, {"head": head, "task_identity": identity}, gates, **kwargs)
            self.assertTrue((fixture.root / "openspec/changes/first").is_dir())

    def test_composition_review_is_not_offered_for_unarchiveable_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.unarchiveable_fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            adapter = SimpleNamespace(github_cli_env=lambda root: {},
                find_exact_head_pr=lambda *a: SimpleNamespace(available=True, stale_open=None),
                ensure_pr=lambda *a, **kw: SimpleNamespace(number=11, url="pr", already_merged=False),
                _pr=lambda *a: {}, _comments=lambda *a: [], _derive=lambda *a: {},
                _transition=mock.Mock(return_value={}), publish_job=mock.Mock())
            with mock.patch.object(workers, "prepare_checkout", return_value=fixture.root), \
                    self.assertRaisesRegex(contributions.ContributionError, "not archiveable.*second"):
                composition.publish_composition(fixture.root, "acme/project", fixture.manifest, head, adapter=adapter)
            adapter._transition.assert_not_called()
            adapter.publish_job.assert_not_called()

    def test_partial_archive_resume_then_repeated_finalization_archives_each_child_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            job = {"head": head, "task_identity": identity}
            gates = {"review": {"result": "passed", "identity": identity, "evidence": {"reviewed": True}}}
            archived = []
            def archive(checkout, name, env):
                self.assertEqual(env["DEV_PLATFORM_COMPOSITION_FINALIZATION"], REQUIREMENT)
                target = checkout / "openspec/changes/archive" / ("2026-10-06-" + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                (checkout / "openspec/changes" / name).rename(target)
                archived.append(name)
                if len(archived) == 1:
                    raise RuntimeError("interrupted mid-archive")
            kwargs = {"source_repo": str(fixture.root), "branch": "requirement/BR-7", "current_head": lambda: head,
                      "archiver": archive}
            with mock.patch.object(composition, "validate_composition_reports"), mock.patch.object(contributions, "push_fast_forward") as push:
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    composition.execute_composition_finalize(fixture.root, job, gates, **kwargs)
                outcome = composition.execute_composition_finalize(fixture.root, job, gates, **kwargs)
                self.assertEqual(outcome["status"], "finalized")
                self.assertEqual(archived, ["first", "second"])
                self.assertEqual(push.call_count, 1)
                head = outcome["pushed_head"]
                job = {"head": head, "task_identity": outcome["identity"]}
                repeated = composition.execute_composition_finalize(fixture.root, job, outcome["gates"], **kwargs)
                self.assertEqual(repeated["status"], "finalized")
                self.assertIsNone(repeated["pushed_head"])
                self.assertEqual(push.call_count, 1)
                self.assertEqual(archived, ["first", "second"])

    def test_reviewer_git_config_is_never_used_after_llm_step(self):
        import independent_review as review
        import independent_review_runner as reviewer
        import managed_task
        import _platform_common
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); seed = root / "seed"; seed.mkdir()
            fixture = self.fixture(seed)
            head = git(seed, "rev-parse", "HEAD")
            identity = composition.composition_identity(seed, fixture.manifest)
            remote = root / "remote.git"
            git(root, "clone", "--bare", str(seed), str(remote))
            checkout = workers.prepare_checkout(remote.as_uri(), str(root), "llm", head)
            launched = False
            originals = (workers.harness_git, workers._git, _platform_common.run_git)
            def harness(path, *args, **kwargs):
                if launched and path == checkout:
                    raise AssertionError("Git used the reviewer checkout after launch")
                return originals[0](path, *args, **kwargs)
            def worker_git(path, *args):
                if launched and path == checkout:
                    raise AssertionError("Git used the reviewer checkout after launch")
                return originals[1](path, *args)
            def common_git(args, **kwargs):
                if launched and kwargs.get("cwd") == checkout:
                    raise AssertionError("Git used the reviewer checkout after launch")
                return originals[2](args, **kwargs)
            def perspective(path, request, name, **kwargs):
                nonlocal launched
                launched = True
                self.assertEqual(kwargs["watched"], [])
                # Model-written Git configuration must never enter the trusted harness.
                (checkout / ".git/config").write_text("[core]\n hooksPath = /malicious-hooks\n")
                return reviewer._report(request, name, {
                    "runtime": "test-runtime", "context_id": name, "fresh_context": True, "write_access": False,
                    "launch_evidence": review.PLATFORM_OBSERVED, "read_only_mechanism": "test-readonly",
                    "model": {"value": "test-model", "source": "test"}}, launched_at="2026-10-06T00:00:00Z", output_sha256="a" * 64)
            with mock.patch.object(reviewer, "preflight", return_value={"ready": True, "provider": "codex", "model": "test-model", "binary": "test-cli"}), mock.patch.object(
                reviewer, "run_perspective", side_effect=perspective
            ), mock.patch.object(managed_task, "fetch_issue", return_value={"body": "Deliver both children"}), mock.patch.object(
                workers, "harness_git", side_effect=harness
            ), mock.patch.object(workers, "_git", side_effect=worker_git), mock.patch.object(_platform_common, "run_git", side_effect=common_git):
                outcome = composition.execute_composition_review(checkout, {"head": head, "task_identity": identity},
                    source_repo=remote.as_uri(), branch="requirement/BR-7", current_head=lambda: head,
                    trusted_root=seed, review_config={}, launcher=mock.Mock())
            self.assertEqual(outcome["status"], "reviewed")
            self.assertNotEqual(outcome["pushed_head"], head)
            self.assertEqual(len(outcome["reports"]), 2)
            self.assertNotIn("malicious-hooks", (root / "harness/.git/config").read_text())

    def run_private_composition_review(self, root, body):
        """Review a private-lineage composition; returns (outcome, remote) with the trusted root configured."""
        import independent_review as review
        import independent_review_runner as reviewer
        import managed_task
        seed = root / "seed"; seed.mkdir()
        fixture = self.fixture(seed)
        head = git(seed, "rev-parse", "HEAD")
        identity = composition.composition_identity(seed, fixture.manifest)
        remote = root / "remote.git"
        git(root, "clone", "--bare", str(seed), str(remote))
        checkout = workers.prepare_checkout(remote.as_uri(), str(root), "llm", head)
        trusted = root / "trusted"; (trusted / "scripts").mkdir(parents=True)
        (trusted / "scripts/check_private_backlog_refs.py").write_text(
            (Path(__file__).resolve().parents[1] / "scripts/check_private_backlog_refs.py").read_text())
        (trusted / ".dev-platform.toml").write_text(platform_config_text(extra='[development_backlog]\nrepository = "acme/private-backlog"'))
        def perspective(path, request, name, **kwargs):
            return reviewer._report(request, name, {
                "runtime": "test-runtime", "context_id": name, "fresh_context": True, "write_access": False,
                "launch_evidence": review.PLATFORM_OBSERVED, "read_only_mechanism": "test-readonly",
                "model": {"value": "test-model", "source": "test"}}, launched_at="2026-10-06T00:00:00Z", output_sha256="a" * 64)
        resolved = []
        def private_requirement(trusted_root, manifest):
            resolved.append(trusted_root)
            return REQUIREMENT
        with mock.patch.object(reviewer, "preflight", return_value={"ready": True, "provider": "codex", "model": "test-model", "binary": "test-cli"}), \
                mock.patch.object(reviewer, "run_perspective", side_effect=perspective), \
                mock.patch.object(managed_task, "fetch_issue", return_value={"body": body}) as fetch, \
                mock.patch.object(composition, "private_lineage_requirement", return_value=True), \
                mock.patch.object(contributions, "private_requirement", side_effect=private_requirement):
            try:
                outcome = composition.execute_composition_review(checkout, {"head": head, "task_identity": identity},
                    source_repo=remote.as_uri(), branch="requirement/BR-7", current_head=lambda: head,
                    trusted_root=trusted, review_config={}, launcher=mock.Mock())
            finally:
                self.assertEqual(resolved, [trusted])
                self.assertEqual(fetch.call_args.args[0], trusted)
        return outcome, remote, head

    def test_private_composition_review_publishes_only_the_outcome(self):
        body = "## Outcome\n\nDeliver both children together.\n\n## Children\n\n- acme/private-backlog#8\n- acme/private-backlog#9\n"
        with tempfile.TemporaryDirectory() as tmp:
            outcome, remote, head = self.run_private_composition_review(Path(tmp), body)
            self.assertEqual(outcome["status"], "reviewed")
            pushed = outcome["pushed_head"]
            published = git(Path(tmp), "--git-dir", str(remote), "diff", head, pushed)
            self.assertIn("Deliver both children together.", published)
            self.assertNotIn("private-backlog#", published)
            self.assertNotIn("private-backlog#", git(Path(tmp), "--git-dir", str(remote), "log", "--format=%B", f"{head}..{pushed}"))

    def test_private_reference_in_the_outcome_blocks_composition_evidence(self):
        body = "## Outcome\n\nFinish what acme/private-backlog#8 started.\n"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(workers.WorkerError, "direct private Backlog reference"):
                self.run_private_composition_review(Path(tmp), body)
            remote = Path(tmp) / "remote.git"
            self.assertEqual(git(Path(tmp), "--git-dir", str(remote), "rev-list", "--count", "--all", "--not",
                                 git(Path(tmp), "--git-dir", str(remote), "rev-parse", "requirement/BR-7")), "0")

    def test_contribution_error_is_a_posted_failed_result_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed"; seed.mkdir()
            fixture = self.fixture(seed)
            head = git(seed, "rev-parse", "HEAD")
            identity = composition.composition_identity(seed, fixture.manifest)
            remote = root / "remote.git"
            git(root, "clone", "--bare", str(seed), str(remote))
            job = {"kind": "review", "number": 11, "head": head, "attempt": 1, "task_identity": identity}
            posted = []
            (root / "work").mkdir()
            missing = contributions.ContributionError("private Requirement resolution needs configured Backlog")
            with mock.patch.object(composition, "private_lineage_requirement", return_value=True), \
                    mock.patch.object(contributions, "private_requirement", side_effect=missing):
                outcome = workers.execute_job(
                    job, source_repo=remote.as_uri(), branch="requirement/BR-7", allowed_paths=[], llm_command=[],
                    current_head=lambda: head, post_result=posted.append, workdir=str(root / "work"), worker="w",
                    review_handler=lambda checkout: composition.execute_composition_review(
                        checkout, job, source_repo=remote.as_uri(), branch="requirement/BR-7",
                        current_head=lambda: head, trusted_root=seed, review_config={}, launcher=mock.Mock()))
            self.assertEqual(outcome["status"], "failed")
            self.assertIn("needs configured Backlog", outcome["cause"])
            self.assertEqual(len(posted), 1)
            self.assertEqual(json.loads(posted[0].removeprefix(workers.RESULT_PREFIX))["outcome"], "failed")
            self.assertTrue(workers.job_completed(job, [{"id": 1, "author_association": "OWNER", "body": posted[0]}]))

    def test_requirement_outcome_requires_its_section(self):
        self.assertEqual(composition.requirement_outcome("Intro\n## Outcome\nShip it.\n## Context\nx\n"), "Ship it.")
        with self.assertRaisesRegex(workers.WorkerError, "no `## Outcome` section"):
            composition.requirement_outcome("## Context\nx\n")
        with self.assertRaisesRegex(workers.WorkerError, "section is empty"):
            composition.requirement_outcome("## Outcome\n\n## Context\nx\n")

    def finalized_adapter(self, head, candidate, events):
        pr = {"head": {"sha": head}, "merged": False, "draft": True, "html_url": "https://example.test/pr/11"}
        return SimpleNamespace(_pr=lambda *a: pr, _comments=lambda *a: [], _derive=lambda *a: candidate,
            publish_job=mock.Mock(side_effect=AssertionError("no pre-merge job is published")),
            _transition=lambda *a, **kw: (events.append(a[3]), candidate.update(gates=kw["gates"])),
            observe_checks=lambda *a: {"head": head, "kind": "passed", "checks": []},
            github_cli_env=lambda root: {}, set_pr_draft=lambda *a, **kw: events.append("undraft"),
            admit=lambda *a: events.append("admit"),
            trusted_apps=lambda *a: frozenset(), trusted_writers=lambda *a: frozenset())

    def test_finalized_composition_goes_to_full_checks_without_a_requirement_retrospective(self):
        import requirement_retrospective as retrospective
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            candidate = {"number": 11, "head": head, "task_identity": identity,
                         "state": "blocked-retryable", "gates": {"review": gate, "finalization": gate}}
            events = []
            adapter = self.finalized_adapter(head, candidate, events)
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options) if "composition-child-" in temporary else fixture.root), \
                    mock.patch.object(composition, "require_final_gates"), \
                    mock.patch("_platform_common.github_cli_env", return_value={}), \
                    mock.patch("project_publish._set_pr_draft", side_effect=lambda *a, **kw: events.append("undraft")), \
                    mock.patch.object(retrospective, "require_checkpoint",
                                      side_effect=AssertionError("no Requirement checkpoint before the merge")):
                result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11,
                                                               adapter=adapter, full_checks=lambda *a: events.append("checks"))
            self.assertEqual(result["status"], "queued")
            self.assertEqual(events, ["blocked-retryable", "checks", "blocked-retryable", "ready", "undraft", "admit"])
            self.assertNotIn("requirement-retrospective", candidate["gates"])

    def test_carried_composition_is_ready_without_the_local_receipt_file(self):
        import requirement_retrospective as retrospective
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            original_checkout = workers.prepare_checkout
            carried = {"number": 11, "head": head, "task_identity": identity, "state": "ready",
                       "gates": {"review": gate, "finalization": gate, "full-checks": gate}}
            adapter = SimpleNamespace(_pr=lambda *a: {"head": {"sha": head}, "merged": False, "draft": False},
                _comments=lambda *a: [], _derive=mock.Mock(side_effect=AssertionError("carried record must be used")),
                publish_job=mock.Mock(), _transition=mock.Mock(), github_cli_env=lambda root: {},
                observe_checks=lambda *a: {"head": head, "kind": "passed", "checks": []},
                trusted_apps=lambda *a: frozenset(), trusted_writers=lambda *a: frozenset())
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options: original_checkout(source, temporary, name, ref, **options) if "composition-child-" in temporary else fixture.root), \
                 mock.patch.object(composition, "require_final_gates"), \
                 mock.patch("_platform_common.github_cli_env", return_value={}), \
                 mock.patch.object(retrospective, "require_checkpoint",
                                   side_effect=AssertionError("the local receipt file is absent in CI")):
                result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11,
                                                               adapter=adapter, enqueue=False, candidate=carried,
                                                               full_checks=mock.Mock())
            self.assertEqual(result["status"], "ready")
            adapter.publish_job.assert_not_called()
            gates = adapter._transition.call_args.kwargs["gates"]
            self.assertNotIn("requirement-retrospective", gates)
            self.assertEqual(gates["full-checks"]["evidence"], {"head": head})

    def test_pending_ci_resumes_without_running_full_checks_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            candidate = {"number": 11, "head": head, "task_identity": identity,
                         "state": "blocked-retryable", "gates": {"review": gate, "finalization": gate}}
            events = []
            adapter = self.finalized_adapter(head, candidate, events)
            adapter.observe_checks = mock.Mock(side_effect=[
                {"head": head, "kind": "pending", "detail": "running", "checks": []},
                {"head": head, "kind": "passed", "detail": "passed", "checks": []},
            ])
            full = mock.Mock()
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options)
                                   if "composition-child-" in temporary else fixture.root), \
                    mock.patch.object(composition, "require_final_gates"), \
                    mock.patch("_platform_common.github_cli_env", return_value={}), \
                    mock.patch("project_publish._set_pr_draft"):
                first = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11,
                                                               adapter=adapter, full_checks=full)
                self.assertEqual(first["status"], "waiting-ci")
                self.assertEqual(candidate["gates"]["required-checks"]["evidence"]["phase"], "composition-final-ci")
                self.assertNotIn("admit", events)
                second = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11,
                                                                adapter=adapter, full_checks=full)
            self.assertEqual(second["status"], "queued")
            self.assertEqual(full.call_count, 1)
            self.assertEqual(events.count("admit"), 1)

    def test_main_only_merge_carries_original_full_check_evidence_without_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            old = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": old}}
            candidate = {"number": 11, "head": old, "task_identity": identity, "state": "ready",
                         "gates": {"review": gate, "finalization": gate, "full-checks": gate}}
            git(fixture.root, "switch", "main")
            (fixture.root / "unrelated-main.txt").write_text("main update\n")
            base = fixture.commit("main update")
            git(fixture.root, "update-ref", "refs/remotes/origin/main", base)
            git(fixture.root, "switch", "requirement/BR-7")
            git(fixture.root, "merge", "--no-ff", base, "-m", "merge main")
            head = git(fixture.root, "rev-parse", "HEAD")
            adapter = self.finalized_adapter(head, candidate, [])
            adapter.observe_checks = mock.Mock(return_value={"head": head, "kind": "pending", "detail": "running"})
            checks = mock.Mock()
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options)
                                   if "composition-child-" in temporary else fixture.root):
                result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11,
                    adapter=adapter, candidate=candidate, main_base=base, enqueue=False, full_checks=checks)
            self.assertEqual(result["status"], "waiting-ci")
            checks.assert_not_called()
            evidence = candidate["gates"]["full-checks"]["evidence"]
            self.assertEqual(evidence["head"], old)
            self.assertEqual(evidence["main_only_bindings"], [{"old_head": old, "base": base, "head": head}])
            composition.require_full_check_evidence(fixture.root, fixture.root, candidate["gates"]["full-checks"],
                                                    candidate["gates"]["full-checks"]["identity"], head)
            invalid = copy.deepcopy(candidate["gates"]["full-checks"])
            invalid["evidence"]["main_only_bindings"][0]["head"] = old
            with self.assertRaises(contributions.ContributionError):
                composition.require_full_check_evidence(fixture.root, fixture.root, invalid, invalid["identity"], head)

    def test_failed_or_stale_ci_never_makes_composition_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            for observation in ({"head": head, "kind": "failed", "detail": "CI failed"},
                                {"head": "f" * 40, "kind": "passed", "detail": "stale"},
                                {"head": head, "kind": "unknown", "detail": "unavailable"}):
                with self.subTest(observation=observation):
                    candidate = {"number": 11, "head": head, "task_identity": identity, "state": "blocked-retryable",
                                 "gates": {"review": gate, "finalization": gate, "full-checks": gate}}
                    events = []
                    adapter = self.finalized_adapter(head, candidate, events)
                    adapter.observe_checks = mock.Mock(return_value=observation)
                    adapter._transition = mock.Mock(side_effect=adapter._transition)
                    original_checkout = workers.prepare_checkout
                    with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                           original_checkout(source, temporary, name, ref, **options)
                                           if "composition-child-" in temporary else fixture.root):
                        result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest,
                                                                       head, 11, adapter=adapter)
                    self.assertEqual(result["status"], "waiting-ci")
                    self.assertNotIn("ready", events)
                    self.assertNotIn("admit", events)
                    self.assertEqual(adapter._transition.call_args.kwargs["red_gate"]["name"], "required-checks")

    def test_failed_full_checks_record_a_named_block_and_propagate(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            candidate = {"number": 11, "head": head, "task_identity": identity,
                         "state": "blocked-retryable", "gates": {"review": gate, "finalization": gate}}
            adapter = self.finalized_adapter(head, candidate, [])
            adapter._transition = mock.Mock(return_value={})
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options)
                                   if "composition-child-" in temporary else fixture.root):
                with self.assertRaisesRegex(RuntimeError, "validation unavailable"):
                    composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11,
                        adapter=adapter, full_checks=mock.Mock(side_effect=RuntimeError("validation unavailable")))
            self.assertIn("validation unavailable", adapter._transition.call_args.kwargs["red_gate"]["evidence"])

    def test_malformed_trusted_result_receipt_fails_explicitly(self):
        head = "a" * 40
        broken = {"id": 7, "body": workers.RESULT_PREFIX + "{not json", "user": {"login": "owner"}, "author_association": "OWNER"}
        untrusted = {"id": 9, "body": workers.RESULT_PREFIX + "{not json", "user": {"login": "someone"}, "author_association": "NONE"}
        self.assertEqual(lifecycle.job_outcomes(head, [untrusted]), {})
        with self.assertRaisesRegex(lifecycle.MalformedMarkerError, "malformed trusted job result comment 7"):
            lifecycle.job_outcomes(head, [broken])
        merged = {"number": 11, "head": head, "task_identity": {"change": "x"}, "attempts": {"post-merge": 1}}
        with self.assertRaisesRegex(lifecycle.MalformedMarkerError, "comment 7"):
            lifecycle.post_merge_job(merged, [broken])

    def test_full_final_head_checks_precede_ready_and_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            for name in ("first", "second"):
                source = fixture.root / "openspec/changes" / name
                target = fixture.root / "openspec/changes/archive" / ("2026-10-06-" + name)
                target.parent.mkdir(parents=True, exist_ok=True); source.rename(target)
            head = fixture.commit("archive all")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            candidate = {"head": head, "task_identity": identity, "gates": {"review": gate, "finalization": gate}}
            events = []
            pr = {"head": {"sha": head}, "draft": True, "html_url": "https://example.test/pr/11"}
            adapter = SimpleNamespace(_pr=lambda *args: pr, _comments=lambda *args: [], _derive=lambda *args: candidate,
                _transition=lambda *args, **kw: (events.append(args[3]), candidate.update(gates=kw["gates"])),
                observe_checks=lambda *a: {"head": head, "kind": "passed", "checks": []},
                github_cli_env=lambda root: {}, set_pr_draft=lambda *args, **kw: events.append("undraft"),
                admit=lambda *args: events.append("admit"))
            kwargs = {"adapter": adapter, "full_checks": lambda *args: events.append("checks")}
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options) if "composition-child-" in temporary else fixture.root), \
                 mock.patch("_platform_common.github_cli_env", return_value={}), \
                 mock.patch("project_publish._set_pr_draft", side_effect=lambda *a, **kw: events.append("undraft")):
                result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11, **kwargs)
                self.assertEqual(result["status"], "queued")
                self.assertEqual(events, ["blocked-retryable", "checks", "blocked-retryable", "ready", "undraft", "admit"])
                self.assertEqual(candidate["gates"]["full-checks"]["evidence"], {"head": head})
                events.clear()
                composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11, **kwargs)
                self.assertNotIn("checks", events)
                candidate["gates"].pop("full-checks")
                default = {k: v for k, v in kwargs.items() if k != "full_checks"}
                with mock.patch.object(integration, "_run_full_checks") as checks:
                    composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11, **default)
                self.assertEqual(checks.call_args.kwargs, {"trusted_root": fixture.root})


class CompositionRepairTests(unittest.TestCase):
    fixture = CompositionTests.fixture

    def request_adapter(self, fixture):
        import publication_queue as queue

        head = git(fixture.root, "rev-parse", "HEAD")
        identity = composition.composition_identity(fixture.root, fixture.manifest)
        current = {"number": 11, "head": head, "state": "finalize-pending", "task_identity": identity,
                   "attempts": {"review": 1}, "gates": {}, "next_job": None, "provider_switch": None}
        pr = {"state": "open", "merged": False, "number": 11,
              "head": {"ref": "requirement/BR-7", "sha": head}, "base": {"ref": "main"}}

        def transition(_root, _repo, _number, state, observed_head, **options):
            current.update(state=state, head=observed_head, next_job=options["next_job"],
                           attempts=options["set_attempts"], red_gate=options["red_gate"])
            return current

        return SimpleNamespace(_pr=mock.Mock(return_value=pr), _comments=mock.Mock(return_value=[]),
            _derive=mock.Mock(return_value=current), _latest=mock.Mock(return_value=current),
            _malformed=mock.Mock(return_value=False), _repair_route=queue._repair_route,
            trusted_apps=mock.Mock(return_value=frozenset()), trusted_writers=mock.Mock(return_value=frozenset()),
            _actor=mock.Mock(return_value="coordinator"), _transition=mock.Mock(side_effect=transition))

    def request(self, fixture, adapter):
        return composition.request_repair(fixture.root, "acme/project", 11,
            expected_head=git(fixture.root, "rev-parse", "HEAD"), reason="Fix cross-child contract wording",
            adapter=adapter, source_repo=str(fixture.root))

    def test_request_enqueues_one_existing_repair_job_with_reason_and_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            adapter = self.request_adapter(fixture)
            result = self.request(fixture, adapter)
            self.assertTrue(result["changed"])
            self.assertEqual(result["job"]["kind"], "repair")
            self.assertEqual(result["job"]["providers"], ["claude"])
            self.assertEqual(result["job"]["reoffer"]["actor"], "coordinator")
            brief = review_gate.repair_brief(adapter._derive.return_value)
            self.assertEqual(brief["findings"][0]["summary"], "Fix cross-child contract wording")
            repeated = self.request(fixture, adapter)
            self.assertFalse(repeated["changed"])
            adapter._transition.assert_called_once()
            self.assertTrue({"blocked-escalation", "blocked-retryable", "repairing"}
                            <= adapter._transition.call_args.kwargs["refuse_from"])

    def test_request_refuses_noncomposition_stale_incomplete_or_claimed_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            adapter = self.request_adapter(fixture)
            pr = adapter._pr.return_value
            for field, value in (("ref", "agent/first"), ("sha", "a" * 40)):
                before = pr["head"][field]
                pr["head"][field] = value
                with self.subTest(field=field), self.assertRaises(contributions.ContributionError):
                    self.request(fixture, adapter)
                pr["head"][field] = before
            original = adapter._derive.return_value["task_identity"]
            adapter._derive.return_value["task_identity"] = {"kind": "contribution"}
            with self.assertRaisesRegex(contributions.ContributionError, "composition record"):
                self.request(fixture, adapter)
            adapter._derive.return_value["task_identity"] = original
            current = adapter._derive.return_value
            current["next_job"] = workers.job_record("review", current["head"], original, 1, providers=["claude"])
            with mock.patch.object(workers, "winning_claim", return_value={"worker": "busy", "expires_at": "later"}), \
                    self.assertRaisesRegex(contributions.ContributionError, "claimed by busy"):
                self.request(fixture, adapter)
            manifest = contributions.seal({**fixture.manifest, "children": fixture.manifest["children"][:1]})
            with mock.patch.object(composition, "candidate_manifest", return_value=manifest), \
                    self.assertRaisesRegex(contributions.ContributionError, "mandatory contribution"):
                self.request(fixture, adapter)
            adapter._transition.assert_not_called()

    def test_request_preserves_recorded_provider_switch_and_refuses_exhaustion(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            adapter = self.request_adapter(fixture)
            current = adapter._derive.return_value
            current["provider_switch"] = {"repair": ["codex"]}
            self.assertEqual(self.request(fixture, adapter)["job"]["providers"], ["codex"])
            current.update(state="finalize-pending", attempts={"repair": review_gate.MAX_ROUNDS})
            with self.assertRaisesRegex(contributions.ContributionError, "rounds exhausted"):
                self.request(fixture, adapter)
            self.assertEqual(adapter._transition.call_count, 1)

    def run_repair(self, fixture, workdir, edit, *, declared=()):
        head = git(fixture.root, "rev-parse", "HEAD")
        identity = composition.composition_identity(fixture.root, fixture.manifest)
        job = {"number": 11, **workers.job_record("repair", head, identity, 1, providers=["claude"])}
        posted = []

        def launch(_command, checkout, **_options):
            edit(checkout)
            return subprocess.CompletedProcess([], 0, "", "")

        workdir.mkdir()
        with mock.patch("_platform_common.generated_files", return_value=declared), \
                mock.patch.object(workers, "push_validated") as push:
            result = workers.execute_job(job, source_repo=str(fixture.root), branch="requirement/BR-7",
                allowed_paths=["first.txt"], llm_command=["writer", "repair"], current_head=lambda: head,
                post_result=posted.append, workdir=str(workdir), worker="test-worker", provider="claude",
                launch=launch, trusted_root=fixture.root)
        return result, push, posted

    def test_repair_regenerates_declared_output_and_composition_manifest_before_validation_and_push(self):
        from _platform_common import GeneratedFile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            fixture = self.fixture(root / "repo")
            manifest_path = fixture.root / integration._candidate_manifest_path(REQUIREMENT, fixture.root)
            manifest_path.write_text(json.dumps(fixture.manifest))  # valid, noncanonical serialization
            fixture.commit("compact manifest")
            generator = root / "generate.py"
            generator.write_text("from pathlib import Path\nimport sys\np = Path(sys.argv[1])\n"
                                 "(p / 'generated.txt').write_text((p / 'first.txt').read_text())\n")
            declared = (GeneratedFile("generated.txt", (sys.executable, str(generator), "{tree}"), ("true",)),)
            original_validate = composition.validate_children
            validated = []

            def validate(checkout, manifest):
                if checkout.name == "writer-stage":
                    self.assertEqual((checkout / "generated.txt").read_text(), "repaired\n")
                    self.assertEqual((checkout / manifest_path.relative_to(fixture.root)).read_text(),
                                     json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                    validated.append(checkout)
                return original_validate(checkout, manifest)

            with mock.patch.object(composition, "validate_children", side_effect=validate):
                result, push, _ = self.run_repair(fixture, root / "job",
                    lambda checkout: (checkout / "first.txt").write_text("repaired\n"), declared=declared)
            self.assertEqual(result["status"], "pushed")
            self.assertEqual(len(validated), 1)
            push.assert_called_once()
            harness = push.call_args.args[0]
            self.assertEqual(git(harness, "show", f"{result['pushed_head']}:generated.txt"), "repaired")
            self.assertIn("Bind reviewed Requirement contributions", git(harness, "log", "-3", "--format=%s"))

    def test_writer_receipt_edit_is_rejected_before_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            fixture = self.fixture(root / "repo")
            result, push, posted = self.run_repair(fixture, root / "job", lambda checkout:
                (checkout / "openspec/changes/first/verification.md").write_text("forged\n"))
            self.assertEqual(result["status"], "rejected")
            self.assertIn("openspec/changes/first/verification.md", posted[-1])
            push.assert_not_called()

    def test_manifest_only_regeneration_does_not_require_an_artificial_writer_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            fixture = self.fixture(root / "repo")
            manifest_path = fixture.root / integration._candidate_manifest_path(REQUIREMENT, fixture.root)
            manifest_path.write_text(json.dumps(fixture.manifest))
            fixture.commit("compact manifest")
            result, push, _ = self.run_repair(fixture, root / "job", lambda _checkout: None)
            self.assertEqual(result["status"], "pushed")
            push.assert_called_once()
            changed = git(push.call_args.args[0], "diff", "--name-only", "HEAD", result["pushed_head"])
            self.assertEqual(changed, manifest_path.relative_to(fixture.root).as_posix())

    def test_generator_receipt_edit_fails_child_validation_before_push(self):
        from _platform_common import GeneratedFile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            fixture = self.fixture(root / "repo")
            generator = root / "corrupt.py"
            generator.write_text("from pathlib import Path\nimport sys\n"
                "(Path(sys.argv[1]) / 'openspec/changes/first/independent-reviews/spec-fidelity.json').write_text('{}')\n")
            declared = (GeneratedFile("openspec/changes/first/independent-reviews/spec-fidelity.json",
                                     (sys.executable, str(generator), "{tree}"), ("true",)),)
            result, push, posted = self.run_repair(fixture, root / "job",
                lambda checkout: (checkout / "first.txt").write_text("repair\n"), declared=declared)
            self.assertEqual(result["status"], "failed")
            self.assertIn("child first receipt changed", posted[-1])
            self.assertIn("independent-reviews/spec-fidelity.json", posted[-1])
            push.assert_not_called()

    def test_every_receipt_is_byte_preserved_after_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            archived = fixture.root / "openspec/changes/archive/2026-11-01-first"
            archived.parent.mkdir()
            (fixture.root / "openspec/changes/first").rename(archived)
            head = fixture.commit("archive first")
            composition.validate_children(fixture.root, fixture.manifest)
            for filename in ("verification.md", "automated-checks.json", "independent-review-request.json",
                             "independent-reviews/spec-fidelity.json"):
                path = archived / filename
                original = path.read_bytes()
                # Even CRLF -> LF in a report must fail; a text read would conceal it.
                path.write_bytes(original.replace(b"\r\n", b"\n") if b"\r\n" in original else original + b" ")
                fixture.commit("receipt drift")
                with self.subTest(filename=filename), self.assertRaisesRegex(contributions.ContributionError,
                                                                                 "child first receipt changed"):
                    composition.validate_children(fixture.root, fixture.manifest)
                path.write_bytes(original)
                fixture.commit("restore fixture receipt")
            self.assertNotEqual(git(fixture.root, "rev-parse", "HEAD"), head)

    def test_reviewed_crlf_receipt_is_validated_without_text_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Repository(Path(tmp))
            first = fixture.child("first", 8)
            receipt = fixture.root / "openspec/changes/first/verification.md"
            receipt.write_bytes(b"Actual fixture evidence\r\n")
            first["head"] = fixture.commit("reviewed CRLF receipt")
            first["gates"]["required-checks"]["evidence"]["head"] = first["head"]
            first["gates"]["semantic-verification"]["evidence"] = review_gate.file_reference(fixture.root, receipt)
            fixture.integrate(first)
            fixture.integrate(fixture.child("second", 9))
            composition.validate_children(fixture.root, fixture.manifest)

    def test_repair_cli_dispatches_only_repair_and_reports_a_refusal(self):
        argv = ["repair", "--pr", "11", "--expected-head", "a" * 40, "--reason", "Fix wording"]
        with mock.patch.object(execution, "current_worktree_root", return_value=Path("/task")), \
                mock.patch.object(execution.managed_task, "origin_repository", return_value="acme/project"), \
                mock.patch.object(composition, "request_repair", side_effect=contributions.ContributionError("incomplete")) as request, \
                mock.patch.object(execution, "advance") as advance, mock.patch("builtins.print") as output:
            self.assertEqual(execution.main(argv), 2)
        request.assert_called_once_with(Path("/task"), "acme/project", 11,
                                       expected_head="a" * 40, reason="Fix wording")
        self.assertIn("incomplete", output.call_args.args[0])
        advance.assert_not_called()


class QueueOwnershipGuardTests(unittest.TestCase):
    def setUp(self):
        import publication_queue
        self.queue = publication_queue

    def test_owned_composition_refuses_before_advance_side_effects(self):
        pr = {"state": "open", "head": {"ref": "requirement/BR-7"}, "base": {"ref": "main"},
              "labels": [{"name": self.queue.QUEUE}]}
        with mock.patch.object(execution, "_contribution_publication_supported", return_value=True), \
             mock.patch.object(self.queue, "_repo", return_value="acme/project"), \
             mock.patch.object(self.queue, "_gh", return_value=[{"number": 11}]), \
             mock.patch.object(self.queue, "_pr", return_value=pr), \
             mock.patch.object(self.queue, "_comments", return_value=[]), \
             mock.patch.object(self.queue, "_derive", return_value={"state": "integrating"}), \
             mock.patch.object(self.queue, "_malformed", return_value=False):
            with self.assertRaisesRegex(execution.RequirementExecutionError, "queue-owned: state integrating"):
                execution._refuse_queue_owned_composition(Path("/unused"), REQUIREMENT)

    def test_advance_refuses_unavailable_queue_before_mutations(self):
        import _platform_common
        root = Path("/unused").resolve()
        with mock.patch.object(_platform_common, "read_platform_config", return_value={"platform_version": "1.0"}), \
             mock.patch.object(execution, "current_worktree_root", return_value=root), \
             mock.patch.object(execution, "_git", return_value="main"), \
             mock.patch.object(execution, "_contribution_publication_supported", return_value=True), \
             mock.patch.object(self.queue, "_repo", side_effect=self.queue.QueueError("queue unavailable")), \
             mock.patch.object(execution.requirement_intake, "fetch_issue") as fetch, \
             mock.patch.object(execution.requirement_board, "claim_started") as claim:
            with self.assertRaisesRegex(execution.RequirementExecutionError,
                                        "cannot observe queue ownership for requirement/BR-7: queue unavailable"):
                execution.advance(root, requirement=REQUIREMENT, base_dir=root)
        fetch.assert_not_called()
        claim.assert_not_called()

    def test_ambiguous_composition_inventory_refuses(self):
        with mock.patch.object(execution, "_contribution_publication_supported", return_value=True), \
             mock.patch.object(self.queue, "_repo", return_value="acme/project"), \
             mock.patch.object(self.queue, "_gh", return_value=[{"number": 11}, {"number": 12}]):
            with self.assertRaisesRegex(execution.RequirementExecutionError, "multiple open"):
                execution._refuse_queue_owned_composition(Path("/unused"), REQUIREMENT)


class SupervisorTests(unittest.TestCase):
    def advance(self, root, graph, children, in_flight=None):
        (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
        ordered = []
        for change, deps in graph.items():
            path = root / (change + ".json")
            path.write_text(json.dumps({"intents": [{"id": change, "dependencies": deps}]}))
            ordered.append((change, path))
        boundary = {"branch": "requirement/BR-7", "head": "a" * 40,
                    "manifest": {"children": children}}
        with mock.patch.object(execution, "_merged_composition", return_value=[]), \
                mock.patch.object(contributions, "in_flight_children", return_value={} if in_flight is None else in_flight), mock.patch.object(contributions, "ensure_integration_branch", return_value=boundary), mock.patch.object(
            execution, "_git"
        ), mock.patch.object(execution.managed_task, "origin_repository", return_value="acme/project"), mock.patch.object(
            execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=root / "child"), "head", False)
        ) as start, mock.patch.object(execution.requirement_board, "reconcile_nonterminal"), mock.patch.object(
            composition, "publish_composition", return_value={"status": "draft-published"}
        ):
            result = execution._advance_contributions(root, REQUIREMENT, ordered,
                {c: f"acme/backlog#{8 + i}" for i, c in enumerate(graph)}, root, False)
        return result, start

    def test_merged_composition_is_listed_before_the_integration_branch_is_touched(self):
        adapter = SimpleNamespace(QueueError=RuntimeError, _gh=mock.Mock(return_value=[{"number": 556}, {"number": 540}]))
        with mock.patch.object(contributions, "ensure_integration_branch") as ensure:
            self.assertEqual(execution._merged_composition(Path("/unused"), REQUIREMENT, "acme/project", adapter=adapter),
                             [540, 556])
        ensure.assert_not_called()
        self.assertEqual(adapter._gh.call_args.args[1:9],
                         ("pr", "list", "--state", "merged", "--head", "requirement/BR-7", "--base", "main"))

    def test_open_or_absent_composition_lets_advance_proceed(self):
        adapter = SimpleNamespace(QueueError=RuntimeError, _gh=mock.Mock(return_value=[]))
        self.assertEqual(execution._merged_composition(Path("/unused"), REQUIREMENT, "acme/project", adapter=adapter), [])

    def test_unreadable_composition_inventory_refuses(self):
        for gh in (mock.Mock(side_effect=RuntimeError("gh exit 1")), mock.Mock(return_value={"bad": 1}),
                   mock.Mock(return_value=[{"number": n} for n in range(100)])):
            with self.subTest(gh=gh), self.assertRaisesRegex(execution.RequirementExecutionError, "inventory of requirement/BR-7"):
                execution._merged_composition(Path("/unused"), REQUIREMENT, "acme/project",
                                              adapter=SimpleNamespace(QueueError=RuntimeError, _gh=gh))

    def test_merged_composition_awaits_post_merge_without_touching_the_branch(self):
        for state, status in (("OPEN", "await-post-merge"), ("CLOSED", "done")):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
                path = root / "first.json"
                path.write_text(json.dumps({"intents": [{"id": "first", "dependencies": []}]}))
                with mock.patch.object(execution, "_merged_composition", return_value=[556]) as check, \
                        mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"state": state}), \
                        mock.patch.object(execution.managed_task, "origin_repository", return_value="acme/project"), \
                        mock.patch.object(contributions, "ensure_integration_branch") as ensure:
                    result = execution._advance_contributions(root, REQUIREMENT, [("first", path)],
                                                              {"first": "acme/backlog#8"}, root, False)
                check.assert_called_once_with(root, REQUIREMENT, "acme/project")
                ensure.assert_not_called()
                self.assertEqual((result["status"], result["composition_pr"], result["children"]),
                                 (status, 556, ["acme/backlog#8"]))
                self.assertEqual(result["status_command"], "python3 scripts/publication_queue.py status --pr 556")

    def test_resume_never_reclaims_coordinator_owned_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
            for state in ("review-pending", "reviewing", "repair-pending", "repairing", "finalize-pending",
                          "blocked-retryable", "integration-repair-pending", "contribution-integration-pending",
                          "contribution-integrated"):
                with self.subTest(state=state):
                    identity = {"kind": "contribution", "change": "first", "requirement": REQUIREMENT,
                                "target_branch": "requirement/BR-7"}
                    adapter = SimpleNamespace(_gh=mock.Mock(return_value=[{"number": 8, "state": "OPEN"}]), _comments=lambda *a: [],
                        _pr=lambda *a: {}, _derive=lambda *a: {}, _malformed=lambda *a: False,
                        _latest=lambda *a: {"state": state, "head": "b" * 40, "task_identity": identity})
                    owned = contributions.in_flight_children(root, "acme/project", REQUIREMENT,
                                                            "requirement/BR-7", adapter=adapter)
                    result, start = self.advance(root, {"first": [], "second": ["first"]}, [], owned)
                    start.assert_not_called()
                    self.assertEqual(result["status"], "await-contributions")
                    self.assertEqual(result["waiting"][0]["state"], state)
                    self.assertIn("coordinator", result["waiting"][0]["reason"])
            adapter._malformed = lambda *a: True
            with self.assertRaisesRegex(contributions.ContributionError, "malformed coordinator ownership"):
                contributions.in_flight_children(root, "acme/project", REQUIREMENT, "requirement/BR-7", adapter=adapter)

    def test_closed_unmerged_contribution_releases_its_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(PROJECT_CONTRACT)
            identity = {"kind": "contribution", "change": "first", "requirement": REQUIREMENT,
                        "target_branch": "requirement/BR-7"}
            latest = {8: {"state": "repair-pending", "head": "b" * 40, "task_identity": identity},
                      9: {"state": "review-pending", "head": "c" * 40, "task_identity": identity}}
            rows = [{"number": 8, "state": "CLOSED"}, {"number": 9, "state": "OPEN"}]
            adapter = SimpleNamespace(_gh=mock.Mock(return_value=rows), _comments=lambda *a: [a[2]],
                _pr=lambda *a: {}, _derive=lambda *a: {}, _malformed=lambda *a: False,
                _latest=lambda root, number, comments: latest[number])
            owned = contributions.in_flight_children(root, "acme/project", REQUIREMENT, "requirement/BR-7", adapter=adapter)
            self.assertEqual(owned["first"]["pr"], 9)
            rows[1:] = []
            self.assertEqual(contributions.in_flight_children(root, "acme/project", REQUIREMENT,
                                                              "requirement/BR-7", adapter=adapter), {})
            rows[:] = [{"number": 8, "state": "OPEN"}, {"number": 9, "state": "OPEN"}]
            with self.assertRaisesRegex(contributions.ContributionError, "ambiguous coordinator ownership"):
                contributions.in_flight_children(root, "acme/project", REQUIREMENT, "requirement/BR-7", adapter=adapter)
            rows[:] = [{"number": 8}]
            with self.assertRaisesRegex(contributions.ContributionError, "unknown state"):
                contributions.in_flight_children(root, "acme/project", REQUIREMENT, "requirement/BR-7", adapter=adapter)

    def test_two_independent_children_start_together_on_same_exact_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, start = self.advance(Path(tmp), {"first": [], "second": []}, [])
            self.assertEqual(result["status"], "implement-children")
            self.assertEqual(start.call_count, 2)
            self.assertEqual(len(result["actions"]), 2)
            self.assertEqual({a["contribution_base"] for a in result["actions"]}, {"a" * 40})

    def test_dependent_child_waits_then_starts_on_integrated_predecessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, start = self.advance(root, {"first": [], "second": ["first"]}, [])
            self.assertEqual(start.call_count, 1)
            self.assertEqual(result["waiting"][0]["dependencies"], ["first"])
            child = {"change": "first", "integrated_head": "b" * 40}
            result, start = self.advance(root, {"first": [], "second": ["first"]}, [child])
            self.assertEqual(start.call_count, 1)
            self.assertEqual(start.call_args.kwargs["contribution"]["dependencies"], [child])
            self.assertEqual(result["actions"][0]["change"], "second")

    def test_third_child_waits_for_both_parallel_predecessors(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = {"first": [], "second": [], "third": ["first", "second"]}
            result, start = self.advance(Path(tmp), graph, [])
            self.assertEqual(start.call_count, 2)
            self.assertEqual(result["waiting"], [{"change": "third", "dependencies": ["first", "second"]}])
            children = [{"change": name, "integrated_head": str(i) * 40} for i, name in enumerate(("first", "second"), 1)]
            result, start = self.advance(Path(tmp), graph, children)
            self.assertEqual(start.call_count, 1)
            self.assertEqual(result["actions"][0]["change"], "third")
            self.assertEqual(start.call_args.kwargs["contribution"]["dependencies"], children)


if __name__ == "__main__":
    unittest.main()
