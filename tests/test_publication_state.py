from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import publication_state  # noqa: E402


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


class PublicationStateTestCase(unittest.TestCase):
    """Shared repo + fake-`gh` harness for exercising publication_state directly."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        git("init", "-b", "main", cwd=self.root)
        git("config", "user.name", "Test", cwd=self.root)
        git("config", "user.email", "test@example.invalid", cwd=self.root)
        (self.root / "file.txt").write_text("base\n", encoding="utf-8")
        git("add", ".", cwd=self.root)
        git("commit", "-m", "base", cwd=self.root)
        git("switch", "-c", "agent/task", cwd=self.root)
        (self.root / "file.txt").write_text("feature\n", encoding="utf-8")
        git("commit", "-am", "feature", cwd=self.root)
        self.head = git("rev-parse", "agent/task", cwd=self.root).stdout.strip()
        self.bin = self.base / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_gh(self, body: str) -> dict[str, str]:
        gh = self.bin / "gh"
        gh.write_text(
            "#!/bin/sh\n"
            # Keep older response snippets focused on the stable PR read while
            # adapting their fake transport to the production candidate list.
            "if [ \"$1\" = pr ] && [ \"$2\" = list ] && ! grep -q '^DIRECT_LIST_FIXTURE=1$' \"$0\"; then\n"
            "  payload=$(\"$0\" pr view \"$6\" --json state,headRefOid); rc=$?\n"
            "  if [ $rc -ne 0 ]; then printf '[]'; exit 0; fi\n"
            "  payload=${payload%?}\n"
            "  base=main\n"
            "  auto=null\n"
            "  printf '[%s,\"number\":9,\"url\":\"https://example.invalid/pr/9\",\"baseRefName\":\"%s\",\"headRefName\":\"%s\",\"autoMergeRequest\":%s}]' \"$payload\" \"$base\" \"$6\" \"$auto\"\n"
            "  exit 0\n"
            "fi\n"
            + body
            + "\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        return env

    def no_pr_gh(self) -> dict[str, str]:
        return self.fake_gh('exit 1\n')


class FindExactHeadPrTests(PublicationStateTestCase):
    def test_exact_local_branch_lookup_uses_registered_branch_head(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"MERGED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_local_branch_pr(self.root, env, "agent/task", "main")
        self.assertTrue(lookup.available)
        self.assertIsNotNone(lookup.exact_merged)

    def test_exact_local_branch_lookup_fails_closed_when_branch_is_missing(self) -> None:
        lookup = publication_state.find_exact_local_branch_pr(self.root, self.no_pr_gh(), "agent/missing", "main")
        self.assertFalse(lookup.available)
        self.assertIn("unavailable", lookup.detail)

    def test_no_pr_reports_no_match(self) -> None:
        lookup = publication_state.find_exact_head_pr(self.root, self.no_pr_gh(), "agent/task", "main", self.head)
        self.assertTrue(lookup.available)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNone(lookup.stale_open)

    def test_exact_open_pr_is_identified_by_state_and_headRefOid(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$4" = "--json" ] && [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$4" = "--json" ] && [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"autoMergeRequest":null,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNotNone(lookup.exact_open)
        self.assertEqual(lookup.exact_open["number"], 9)
        self.assertEqual(lookup.exact_open["url"], "https://example.invalid/pr/9")
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNone(lookup.stale_open)

    def test_closed_unmerged_pr_with_same_head_is_not_a_match(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"CLOSED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNone(lookup.stale_open)

    def test_merged_pr_with_exact_head_is_identified(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"MERGED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNotNone(lookup.exact_merged)
        self.assertIsNone(lookup.exact_open)

    def test_reused_branch_selects_current_exact_pr_not_historical_merged_pr(self) -> None:
        old_head = "a" * 40
        env = self.fake_gh(
            'DIRECT_LIST_FIXTURE=1\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":3,"url":"https://example.invalid/pr/3","state":"MERGED","headRefOid":"{old_head}","baseRefName":"main","headRefName":"agent/task"}},{{"number":4,"url":"https://example.invalid/pr/4","state":"OPEN","headRefOid":"{self.head}","baseRefName":"main","headRefName":"agent/task"}}]\'; exit 0;\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertTrue(lookup.available)
        self.assertEqual(lookup.exact_open["number"], 4)
        self.assertIsNone(lookup.exact_merged)

    def test_open_pr_with_different_head_is_reported_as_stale_not_exact(self) -> None:
        other_head = "0" * 40
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{other_head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNotNone(lookup.stale_open)
        self.assertEqual(lookup.stale_open["headRefOid"], other_head)

    def test_open_pr_targeting_a_different_base_is_not_a_match(self) -> None:
        env = self.fake_gh(
            'DIRECT_LIST_FIXTURE=1\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":9,"url":"https://example.invalid/pr/9","state":"OPEN","headRefOid":"{self.head}","baseRefName":"release/1.0","headRefName":"agent/task"}}]\'; exit 0; fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.stale_open)

    def test_unparseable_response_is_reported_unavailable_not_absent(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            '  if [ "$5" = "state,headRefOid" ]; then echo "not json"; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertFalse(lookup.available)


class ObservePublicationTests(PublicationStateTestCase):
    def observe(self, env: dict[str, str] | None) -> publication_state.PublicationObservation:
        return publication_state.observe_publication(self.root, self.root, env, "agent/task", "main")

    def test_no_authentication_is_reported_as_github_unavailable(self) -> None:
        obs = self.observe(None)
        self.assertEqual(obs.bucket, publication_state.GITHUB_UNAVAILABLE)
        self.assertFalse(obs.github_available)

    def test_no_pr_yet_is_not_published(self) -> None:
        obs = self.observe(self.no_pr_gh())
        self.assertEqual(obs.bucket, publication_state.NOT_PUBLISHED)

    def test_open_pr_with_pending_checks_and_no_arm_is_open_checks_pending(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main","autoMergeRequest":null}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "[]"; exit 0; fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.OPEN_CHECKS_PENDING)
        self.assertFalse(obs.auto_merge_armed)

    def test_open_pr_with_auto_merge_request_is_remote_armed(self) -> None:
        env = self.fake_gh(
            'DIRECT_LIST_FIXTURE=1\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":9,"url":"https://example.invalid/pr/9","state":"OPEN","headRefOid":"{self.head}","baseRefName":"main","headRefName":"agent/task","autoMergeRequest":{{"enabledBy":"agent"}}}}]\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "[]"; exit 0; fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.REMOTE_ARMED)
        self.assertTrue(obs.auto_merge_armed)

    def test_open_pr_with_failed_checks_is_blocked(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  if [ "$5" = "baseRefName" ]; then printf \'{"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"ci","state":"FAILURE","workflow":"ci","link":""}]\'; exit 0; fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.BLOCKED)

    def test_merged_pr_with_local_main_behind_is_pending_local_reconciliation(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"MERGED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        # No origin remote configured, so remote_main_head stays None; local main
        # is present -> mismatched (None != a value is False, so this exercises
        # the "cannot confirm reconciled" default of not-pending here). Add a
        # fake remote to make the mismatch concrete instead.
        remote = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        git("remote", "add", "origin", str(remote), cwd=self.root)
        # Push a *different* main than local, simulating a remote main that has
        # already advanced past what this checkout has fetched/merged locally.
        other = self.base / "other-clone"
        subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
        git("config", "user.name", "Test", cwd=other)
        git("config", "user.email", "test@example.invalid", cwd=other)
        (other / "extra.txt").write_text("extra\n", encoding="utf-8")
        git("add", ".", cwd=other)
        git("commit", "-m", "extra", cwd=other)
        git("push", "origin", "HEAD:main", cwd=other)

        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.REMOTE_MERGED_LOCAL_PENDING)
        self.assertTrue(obs.remote_merged)
        self.assertTrue(obs.local_reconciliation_pending)

    def test_stale_open_pr_for_different_head_reports_detail_without_blocking_new_head(self) -> None:
        other_head = "0" * 40
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{other_head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.NOT_PUBLISHED)
        self.assertIn(other_head, obs.detail)
        self.assertIn(self.head, obs.detail)


class StatusRenderingTests(PublicationStateTestCase):
    def test_status_payload_never_includes_credential_or_env_fields(self) -> None:
        obs = publication_state.observe_publication(self.root, self.root, None, "agent/task", "main")
        payload = publication_state.status_payload(obs, "unknown")
        blob = json.dumps(payload)
        for forbidden in ("GH_TOKEN", "GITHUB_TOKEN", "password", "Authorization"):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(payload["status"], publication_state.GITHUB_UNAVAILABLE)

    def test_status_text_is_human_readable_and_includes_key_fields(self) -> None:
        obs = publication_state.observe_publication(self.root, self.root, self.no_pr_gh(), "agent/task", "main")
        text = publication_state.status_text(obs, "manual")
        self.assertIn("status: not_published", text)
        self.assertIn("merge_durability: manual", text)


class MergeDurabilityCapabilityTests(PublicationStateTestCase):
    def test_manual_merge_mode_reports_manual_without_any_gh_call(self) -> None:
        result = publication_state.merge_durability_capability({"pr_merge_mode": "manual"}, self.no_pr_gh(), self.root)
        self.assertEqual(result, "manual")

    def test_no_env_reports_unknown(self) -> None:
        result = publication_state.merge_durability_capability({"pr_merge_mode": "auto"}, None, self.root)
        self.assertEqual(result, "unknown")

    def test_auto_merge_allowed_reports_remote_armed_capable(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "repo" ] && [ "$2" = "view" ]; then echo "owner/repo"; exit 0; fi\n'
            'if [ "$1" = "api" ]; then echo "true"; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.merge_durability_capability({"pr_merge_mode": "auto"}, env, self.root)
        self.assertEqual(result, "remote_armed_capable")

    def test_auto_merge_disallowed_reports_foreground_fallback(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "repo" ] && [ "$2" = "view" ]; then echo "owner/repo"; exit 0; fi\n'
            'if [ "$1" = "api" ]; then echo "false"; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.merge_durability_capability({"pr_merge_mode": "auto"}, env, self.root)
        self.assertEqual(result, "foreground_fallback")


def _sh(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


SUCCESS_ROW = {"name": "validate", "state": "SUCCESS", "workflow": "Platform CI", "link": "https://example.invalid/run"}
def branch_protection(required):
    return json.dumps({"name": "main", "protected": True, "protection": {"required_status_checks": required}})


REQUIRED_VALIDATE = branch_protection({"contexts": ["validate"], "checks": [{"context": "validate", "app_id": None}]})


class RequiredCheckStateForRefTests(PublicationStateTestCase):
    """Shared classifier behind rollout adoption, finish, queue integration and status.

    Fixtures follow the shapes recorded against gh 2.97: ``pr checks --json`` exits 0 for
    passed, pending and failed lists, and ``--required`` with no required checks exits 1 with
    empty stdout.
    """

    def gh(self, *, heads=("abc123",), base="main", base_rc=0, checks=(0, "[]"), all_checks=None,
           api=(0, "", ""), runs=(0, '[{"check_runs": []}]'), view_rc=0) -> dict[str, str]:
        counter = self.base / "head-count"
        counter.unlink(missing_ok=True)
        head_cases = "".join(f"{i}) printf '{{\"state\":\"OPEN\",\"headRefOid\":\"{h}\"}}';; " for i, h in enumerate(heads[:-1]))
        head_cases += f"*) printf '{{\"state\":\"OPEN\",\"headRefOid\":\"{heads[-1]}\"}}';; "
        required_rc, required_out = checks
        all_rc, all_out = all_checks if all_checks is not None else (0, "[]")
        api_rc, api_out, api_err = api
        runs_rc, runs_out = runs
        self.calls = self.base / "calls.log"
        self.calls.unlink(missing_ok=True)
        body = (
            f'echo "$*" >> {_sh(str(self.calls))}\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ {view_rc} -ne 0 ]; then exit {view_rc}; fi\n'
            '  if [ "$5" = "state,headRefOid" ]; then\n'
            f'    n=$(cat {_sh(str(counter))} 2>/dev/null || echo 0); echo $((n+1)) > {_sh(str(counter))}\n'
            f'    case $n in {head_cases}esac; exit 0\n'
            '  fi\n'
            f'  if [ "$5" = "baseRefName" ]; then if [ {base_rc} -ne 0 ]; then exit {base_rc}; fi; '
            f'printf \'{{"baseRefName":"{base}"}}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then\n'
            '  case " $* " in\n'
            f'    *" --required "*) printf %s {_sh(required_out)}; exit {required_rc};;\n'
            f'    *) printf %s {_sh(all_out)}; exit {all_rc};;\n'
            '  esac\n'
            'fi\n'
            'if [ "$1" = "api" ]; then\n'
            '  case "$*" in *"/protection"*) echo "Administration permission denied" >&2; exit 1;; esac\n'
            f'  case "$*" in *"/check-runs?"*) printf %s {_sh(runs_out)}; exit {runs_rc};; esac\n'
            f'  printf %s {_sh(api_out)}; printf %s {_sh(api_err)} >&2; exit {api_rc}\n'
            'fi\n'
            'exit 1'
        )
        return self.fake_gh(body)

    def observe(self, env: dict[str, str]) -> publication_state.RequiredCheckState:
        result = publication_state.required_check_state_for_ref(self.root, env, "9", "abc123")
        if result.kind == "unknown":
            self.assertIn(result.cause, publication_state.UNKNOWN_CAUSES)
        else:
            self.assertEqual(result.cause, "")
        return result

    def test_passed_pending_and_failed_lists_exit_zero(self) -> None:
        for state, kind in (("SUCCESS", "passed"), ("IN_PROGRESS", "pending"), ("FAILURE", "failed")):
            with self.subTest(state=state):
                rows = json.dumps([{**SUCCESS_ROW, "state": state}])
                self.assertEqual(self.observe(self.gh(checks=(0, rows))).kind, kind)

    def test_exit_zero_empty_list_is_not_registered(self) -> None:
        self.assertEqual(self.observe(self.gh(checks=(0, "[]"))).kind, "not_registered")

    def test_no_required_checks_with_unprotected_base_is_not_registered_from_protection(self) -> None:
        env = self.gh(checks=(1, ""), api=(0, '{"name":"main","protected":false}', ""))
        result = self.observe(env)
        self.assertEqual(result.kind, "not_registered")
        self.assertIn("main", result.detail)
        self.assertIn("api repos/{owner}/{repo}/branches/main\n", self.calls.read_text())

    def test_branch_protection_shape_is_required_for_protected_branch(self) -> None:
        for payload in ({}, {"name": "other", "protected": False},
                        {"name": "main", "protected": "false"},
                        {"name": "main", "protected": True},
                        {"name": "main", "protected": True, "protection": {}},
                        {"name": "main", "protected": True, "protection": {
                            "required_status_checks": {"contexts": [], "checks": None}}}):
            with self.subTest(payload=payload):
                result = self.observe(self.gh(base="requirement/BR-415", api=(0, json.dumps(payload), "")))
                self.assertEqual((result.kind, result.cause), ("unknown", "malformed"))

    def test_no_required_checks_while_base_requires_some_is_pending_expected(self) -> None:
        # A fresh head GitHub has not attached checks to yet: the required contexts are pending, not unusable.
        result = self.observe(self.gh(checks=(1, ""), api=(0, REQUIRED_VALIDATE, "")))
        self.assertEqual((result.kind, result.cause), ("pending", ""))
        self.assertEqual(result.checks, ({"name": "validate", "state": "EXPECTED"},))
        self.assertIn("validate", result.detail)

    def test_protection_api_failure_is_transport(self) -> None:
        result = self.observe(self.gh(checks=(1, ""), api=(1, "", "gh: Server Error (HTTP 500)")))
        self.assertEqual((result.kind, result.cause), ("unknown", "transport"))

    def test_generic_protection_404_is_transport_not_absence(self) -> None:
        for stdout, stderr in (("", "gh: Not Found (HTTP 404)"),
                               ('{"message":"Not Found"}', "gh: Not Found (HTTP 404)"),
                               ('{"message":"Branch not protected"}', "gh: Branch not protected (HTTP 404)")):
            with self.subTest(stdout=stdout):
                result = self.observe(self.gh(checks=(1, ""), api=(1, stdout, stderr)))
                self.assertEqual((result.kind, result.cause), ("unknown", "transport"))

    def test_other_exit_or_exit_one_with_output_is_transport(self) -> None:
        for rc, out in ((2, ""), (4, ""), (8, "[]"), (1, "something")):
            with self.subTest(rc=rc, out=out):
                result = self.observe(self.gh(checks=(rc, out)))
                self.assertEqual((result.kind, result.cause), ("unknown", "transport"))

    def test_garbage_or_wrong_shape_stdout_is_malformed(self) -> None:
        for out in ("not json", '{"name":"x"}', "[1]"):
            with self.subTest(out=out):
                result = self.observe(self.gh(checks=(0, out)))
                self.assertEqual((result.kind, result.cause), ("unknown", "malformed"))

    def test_unsupported_check_state_has_its_own_cause(self) -> None:
        rows = json.dumps([{**SUCCESS_ROW, "state": "WEIRD"}])
        self.assertEqual(self.observe(self.gh(checks=(0, rows))).cause, "unsupported-state")

    def test_pr_view_failures_are_transport_or_malformed(self) -> None:
        self.assertEqual(self.observe(self.gh(view_rc=1)).cause, "transport")
        self.assertEqual(self.observe(self.gh(base_rc=1)).cause, "transport")

    def test_head_differing_before_or_changing_between_calls_is_head_mismatch(self) -> None:
        rows = json.dumps([SUCCESS_ROW])
        for heads in (("def456",), ("abc123", "def456")):
            with self.subTest(heads=heads):
                result = self.observe(self.gh(heads=heads, checks=(0, rows)))
                self.assertEqual((result.kind, result.cause), ("unknown", "head-mismatch"))

    def test_contribution_base_uses_mains_required_checks(self) -> None:
        base = "requirement/BR-415"
        cases = {
            "success": ([SUCCESS_ROW], "passed"),
            "in progress": ([{**SUCCESS_ROW, "state": "IN_PROGRESS"}], "pending"),
            "failure": ([{**SUCCESS_ROW, "state": "FAILURE"}], "failed"),
            "missing required row": ([{**SUCCESS_ROW, "name": "publish-next"}], "pending"),
            "no rows": ([], "pending"),
            "unrelated failing row ignored": ([SUCCESS_ROW, {**SUCCESS_ROW, "name": "other", "state": "FAILURE"}], "passed"),
        }
        for name, (rows, kind) in cases.items():
            with self.subTest(name):
                env = self.gh(base=base, all_checks=(0, json.dumps(rows)), api=(0, REQUIRED_VALIDATE, ""))
                result = self.observe(env)
                self.assertEqual(result.kind, kind)
                if name in {"missing required row", "no rows"}:
                    self.assertEqual(result.checks, ({"name": "validate", "state": "EXPECTED"},))
                log = self.calls.read_text()
                self.assertIn("api repos/{owner}/{repo}/branches/main\n", log)
                self.assertNotIn("/protection", log)
                self.assertNotIn("--required", log)

    def test_contribution_preserves_required_app_binding(self) -> None:
        protection = branch_protection({"contexts": ["validate"], "checks": [{"context": "validate", "app_id": 1}]})
        def run(app, state="success", number=1):
            return {"id": number, "name": "validate", "app": {"id": app}, "head_sha": "abc123",
                    "status": "completed", "conclusion": state}

        cases = [
            ([run(2)], "pending"),
            ([run(1)], "passed"),
            ([run(2), run(1, "failure", 2)], "failed"),
            ([run(1), run(1, "failure", 2)], "failed"),
            ([{**run(1), "status": "in_progress", "conclusion": None}], "pending"),
        ]
        for runs, expected in cases:
            with self.subTest(runs=runs):
                env = self.gh(base="requirement/BR-415", all_checks=(0, json.dumps([SUCCESS_ROW])),
                              api=(0, protection, ""), runs=(0, json.dumps([{"check_runs": []}, {"check_runs": runs}])))
                result = self.observe(env)
                self.assertEqual(result.kind, expected)
                if runs == [run(2)]:
                    # The required App's missing run is unreported, not a run in progress.
                    self.assertEqual(result.checks, ({"name": "validate", "state": "EXPECTED"},))
                self.assertIn("--paginate --slurp", self.calls.read_text())
                self.assertIn("commits/abc123/check-runs", self.calls.read_text())

    def test_bound_protection_app_id_must_be_explicit_and_valid(self) -> None:
        for check in ({"context": "validate"}, {"context": "validate", "app_id": True},
                      {"context": "validate", "app_id": "1"}, {"context": "validate", "app_id": -2}):
            with self.subTest(check=check):
                protection = branch_protection({"contexts": ["validate"], "checks": [check]})
                self.assertEqual(self.observe(self.gh(base="requirement/BR-415",
                                 api=(0, protection, ""))).cause, "malformed")

    def test_any_app_binding_preserves_name_based_checks(self) -> None:
        protection = branch_protection({"contexts": ["validate"], "checks": [{"context": "validate", "app_id": -1}]})
        env = self.gh(base="requirement/BR-415", api=(0, protection, ""),
                      all_checks=(0, json.dumps([SUCCESS_ROW])))
        self.assertEqual(self.observe(env).kind, "passed")
        self.assertNotIn("/check-runs?", self.calls.read_text())

    def test_bound_check_run_observation_fails_closed(self) -> None:
        protection = branch_protection({"contexts": [], "checks": [{"context": "validate", "app_id": 1}]})
        for runs, cause in [((1, ""), "transport"), ((0, "{}"), "malformed"),
                            ((0, '[{"check_runs": [{}]}]'), "malformed"),
                            ((0, '[{"check_runs": [{"id":1,"name":"validate","app":{"id":1},'
                                  '"head_sha":"other","status":"completed","conclusion":"success"}]}]'), "head-mismatch")]:
            with self.subTest(runs=runs):
                self.assertEqual(self.observe(self.gh(base="requirement/BR-415",
                                 api=(0, protection, ""), runs=runs)).cause, cause)

    def test_contribution_base_failures_are_explicit(self) -> None:
        base = "requirement/BR-415"
        self.assertEqual(self.observe(self.gh(base=base, api=(1, "", "HTTP 500"))).cause, "transport")
        self.assertEqual(self.observe(self.gh(base=base, api=(1, "", "gh: Not Found (HTTP 404)"))).cause, "transport")
        self.assertEqual(self.observe(self.gh(base=base, all_checks=(1, "[]"), api=(0, REQUIRED_VALIDATE, ""))).cause, "transport")
        self.assertEqual(self.observe(self.gh(base=base, all_checks=(0, "junk"), api=(0, REQUIRED_VALIDATE, ""))).cause, "malformed")

    def test_unsupported_base_is_unknown_with_cause(self) -> None:
        result = publication_state.required_check_state_for_ref(self.root, self.gh(base="release/1.0"), "9", "abc123")
        self.assertEqual((result.kind, result.cause), ("unknown", "unsupported-state"))
        self.assertIn("release/1.0", result.detail)

    def test_unreadable_pr_state_is_unknown_with_cause(self) -> None:
        result = publication_state.required_check_state_for_ref(self.root, self.no_pr_gh(), "9", "abc123")
        self.assertEqual((result.kind, result.cause), ("unknown", "transport"))

    def test_unknown_requires_a_cause(self) -> None:
        with self.assertRaises(ValueError):
            publication_state.RequiredCheckState("unknown", "no cause")


if __name__ == "__main__":
    unittest.main()
