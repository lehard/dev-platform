"""Requirement contribution and composition boundaries, including resumable Git facts."""
from __future__ import annotations

import collections
import copy
import json
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


class Repository:
    def __init__(self, root, *, committed_contract=True):
        self.root = root
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "Test")
        git(root, "config", "user.email", "test@example.test")
        (root / "AGENTS.md").write_text("Bounded test repository\n")
        (root / ".dev-platform.toml").write_text('platform_version = "1.0.0"\n')  # committed project contract
        if not committed_contract:
            # A source-repository history from before its public contract was committed:
            # the composition checkout only carries an installed, locally excluded contract.
            with (root / ".git" / "info" / "exclude").open("a") as handle:
                handle.write(".dev-platform.toml\n")
        self.base = self.commit("base")
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

    def child(self, name, number):
        git(self.root, "switch", "-c", f"agent/{name}", self.boundary)
        change = self.root / "openspec/changes" / name
        change.mkdir(parents=True)
        (change / "tasks.md").write_text("- [x] Implement child\n")
        (change / "proposal.md").write_text(f"Implement {name}\n")
        (change / "automated-checks.json").write_text("{}\n")
        (change / "verification.md").write_text("Actual fixture evidence\n")
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
            with mock.patch.dict("os.environ", {"GH_TOKEN": token}, clear=True), mock.patch.object(
                workers, "harness_git", side_effect=["", origin]
            ):
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
                with self.assertRaisesRegex(workers.WorkerError, "requires coordinator GH_TOKEN"):
                    workers.harness_push_env(fixture.root, {})
            runner.return_value = subprocess.CompletedProcess([], 1, "", token + encoded)
            with mock.patch.dict("os.environ", {"GH_TOKEN": token}, clear=True), mock.patch.object(
                workers, "harness_git", side_effect=["", origin]
            ), self.assertRaises(contributions.ContributionError) as error:
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
            with mock.patch.dict(os.environ, {"HOME": "/operator-home", "GH_TOKEN": "secret",
                    "GITHUB_TOKEN": "secret", "SSH_AUTH_SOCK": "/agent"}), \
                 mock.patch.object(integration, "_full_check_commands", return_value=["candidate-check"]), \
                 mock.patch.object(integration.subprocess, "run", side_effect=command):
                integration._run_full_checks(root)
            self.assertEqual(len(observed), 1)
            self.assertFalse(Path(observed[0]["HOME"]).exists())

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
            (seed / ".dev-platform.toml").write_text('platform_version = "1.0.0"\n')  # committed project contract
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

    def test_final_gates_require_archive_retrospective_and_exact_checks(self):
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
                     for g in ("review", "finalization", "requirement-retrospective", "full-checks")}
            candidate = {"head": head, "task_identity": identity, "gates": gates}
            composition.require_final_gates(fixture.root, fixture.manifest, candidate, head)
            for name in gates:
                bad = copy.deepcopy(candidate); bad["gates"].pop(name)
                with self.subTest(gate=name), self.assertRaises(contributions.ContributionError):
                    composition.require_final_gates(fixture.root, fixture.manifest, bad, head)
            stale = copy.deepcopy(candidate); stale["gates"]["full-checks"]["evidence"]["head"] = "f" * 40
            with self.assertRaises(contributions.ContributionError):
                composition.require_final_gates(fixture.root, fixture.manifest, stale, head)

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
            def harness(path, *args):
                if launched and path == checkout:
                    raise AssertionError("Git used the reviewer checkout after launch")
                return originals[0](path, *args)
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
                    review_config={}, launcher=mock.Mock())
            self.assertEqual(outcome["status"], "reviewed")
            self.assertNotEqual(outcome["pushed_head"], head)
            self.assertEqual(len(outcome["reports"]), 2)
            self.assertNotIn("malicious-hooks", (root / "harness/.git/config").read_text())

    def test_finalized_composition_offers_and_runs_premerge_parent_retrospective(self):
        import integration_contour as contour
        import requirement_retrospective as retrospective
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head = git(fixture.root, "rev-parse", "HEAD")
            identity = composition.composition_identity(fixture.root, fixture.manifest)
            gate = {"result": "passed", "identity": identity, "evidence": {"head": head}}
            candidate = {"number": 11, "head": head, "task_identity": identity,
                         "state": "blocked-retryable", "gates": {"review": gate, "finalization": gate}}
            adapter = SimpleNamespace(_pr=lambda *a: {"head": {"sha": head}, "merged": False},
                _comments=lambda *a: [], _derive=lambda *a: candidate, publish_job=mock.Mock(), _transition=mock.Mock())
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options) if "composition-child-" in temporary else fixture.root):
                result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11, adapter=adapter)
                self.assertEqual(result["status"], "await-requirement-retrospective")
                self.assertEqual(adapter.publish_job.call_args.args[3], "retrospective")
                candidate["next_job"] = workers.job_record("retrospective", head, identity, 0, phase="pre-merge")
                job = workers.build_job(candidate)
                ops, post = mock.Mock(), mock.Mock()
                with mock.patch.object(contour, "ensure_requirement_checkpoint") as checkpoint, mock.patch.object(
                    retrospective, "require_checkpoint", return_value={"result": "none"}
                ), mock.patch.object(composition, "advance_final_publication", return_value={"status": "queued"}) as publish:
                    outcome = composition.run_claimed_retrospective(fixture.root, "acme/project", candidate, job,
                        source_repo=str(fixture.root), adapter=adapter, ops=ops, post_result=post, claim_current=lambda: True, worker="w")
                self.assertEqual(outcome["status"], "queued")
                checkpoint.assert_called_once_with(ops, fixture.root, REQUIREMENT, ["acme/backlog#8", "acme/backlog#9"])
                self.assertIn("requirement-retrospective", adapter._transition.call_args.kwargs["gates"])
                publish.assert_called_once()
                post.assert_called_once()
                merged = {**candidate, "attempts": {"post-merge": 1}}
                postmerge, _ = lifecycle.post_merge_job(merged, [{"id": 1, "body": post.call_args.args[0],
                    "user": {"login": "owner"}, "author_association": "OWNER"}])
                self.assertEqual(postmerge["kind"], "retrospective")
                self.assertNotEqual(workers.job_id({**postmerge, "number": 11}), workers.job_id(job))

    def test_full_final_head_checks_and_checkpoint_precede_ready_and_admission(self):
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
                _transition=lambda *args, **kw: (events.append("ready"), candidate.update(gates=kw["gates"])),
                github_cli_env=lambda root: {}, set_pr_draft=lambda *args, **kw: events.append("undraft"),
                admit=lambda *args: events.append("admit"))
            kwargs = {"adapter": adapter, "checkpoint": lambda *a, **kw: (events.append("checkpoint") or {"result": "none"}),
                      "full_checks": lambda *args: events.append("checks")}
            original_checkout = workers.prepare_checkout
            with mock.patch.object(workers, "prepare_checkout", side_effect=lambda source, temporary, name, ref, **options:
                                   original_checkout(source, temporary, name, ref, **options) if "composition-child-" in temporary else fixture.root):
                result = composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11, **kwargs)
                self.assertEqual(result["status"], "queued")
                self.assertEqual(events, ["checkpoint", "checks", "ready", "undraft", "admit"])
                events.clear()
                composition.advance_final_publication(fixture.root, "acme/project", fixture.manifest, head, 11, **kwargs)
                self.assertNotIn("checks", events)


class SupervisorTests(unittest.TestCase):
    def advance(self, root, graph, children, in_flight=None):
        ordered = []
        for change, deps in graph.items():
            path = root / (change + ".json")
            path.write_text(json.dumps({"intents": [{"id": change, "dependencies": deps}]}))
            ordered.append((change, path))
        boundary = {"branch": "requirement/BR-7", "head": "a" * 40,
                    "manifest": {"children": children}}
        with mock.patch.object(contributions, "in_flight_children", return_value={} if in_flight is None else in_flight), mock.patch.object(contributions, "ensure_integration_branch", return_value=boundary), mock.patch.object(
            execution, "_git"
        ), mock.patch.object(execution.managed_task, "origin_repository", return_value="acme/project"), mock.patch.object(
            execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=root / "child"), "head", False)
        ) as start, mock.patch.object(execution.requirement_board, "reconcile_nonterminal"), mock.patch.object(
            composition, "publish_composition", return_value={"status": "draft-published"}
        ):
            result = execution._advance_contributions(root, REQUIREMENT, ordered,
                {c: f"acme/backlog#{8 + i}" for i, c in enumerate(graph)}, root, False)
        return result, start

    def test_resume_never_reclaims_coordinator_owned_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for state in ("review-pending", "reviewing", "repair-pending", "repairing", "finalize-pending",
                          "blocked-retryable", "integration-repair-pending", "contribution-integration-pending",
                          "contribution-integrated"):
                with self.subTest(state=state):
                    identity = {"kind": "contribution", "change": "first", "requirement": REQUIREMENT,
                                "target_branch": "requirement/BR-7"}
                    adapter = SimpleNamespace(_gh=mock.Mock(return_value=[{"number": 8}]), _comments=lambda *a: [],
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
