from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_supersession as supersession  # noqa: E402


def pr(number: int, version: str, *, author: str = "dev-platform-bot[bot]", base: str = "main", branch: str | None = None, repository: str = "lehard/managed") -> dict[str, object]:
    branch = branch or f"dev-platform/rollout-{version}"
    return {
        "number": number,
        "html_url": f"https://example.invalid/pr/{number}",
        "user": {"login": author},
        "base": {"ref": base},
        "head": {"ref": branch, "repo": {"full_name": repository}},
    }


class RolloutSupersessionTests(unittest.TestCase):
    def eligible(self, *prs: dict[str, object]) -> list[supersession.RolloutPR]:
        return supersession.eligible_rollout_prs(
            list(prs), repository="lehard/managed", base_branch="main", expected_bot="dev-platform-bot[bot]"
        )

    def test_identity_requires_exact_branch_semver_base_and_bot_not_title(self) -> None:
        eligible = self.eligible(
            pr(1, "v1.2.3"),
            pr(2, "v1.2.2", branch="dev-platform/rollout-v1.2"),
            pr(3, "v1.2.2", author="human"),
            pr(4, "v1.2.2", base="release"),
            pr(5, "v1.2.2", branch="dev-platform/rollout-v1.2.2-extra"),
        )
        self.assertEqual([(item.number, item.version) for item in eligible], [(1, "v1.2.3")])

    def test_coherent_committed_metadata_is_required(self) -> None:
        self.assertEqual(
            supersession.platform_version_from_contents("_commit: v1.3.0\n", 'platform_version = "1.3.0"\n'),
            "v1.3.0",
        )
        self.assertIsNone(
            supersession.platform_version_from_contents("_commit: v1.3.0\n", 'platform_version = "1.2.9"\n')
        )

    def test_newer_validated_pr_closes_only_older_versions(self) -> None:
        eligible = self.eligible(pr(1, "v1.0.0"), pr(2, "v1.1.0"), pr(3, "v1.2.0"))
        plan = supersession.plan_supersession(
            eligible, base_version="v1.0.0", authoritative_version="v1.1.0", authoritative_pr=2
        )
        self.assertEqual([(item.number, reason) for item, reason in plan], [
            (1, "committed downstream base already uses v1.0.0"),
        ])

    def test_committed_base_closes_all_same_or_older_but_keeps_future(self) -> None:
        eligible = self.eligible(pr(1, "v1.0.0"), pr(2, "v1.1.0"), pr(3, "v1.2.0"))
        plan = supersession.plan_supersession(eligible, base_version="v1.1.0", authoritative_version=None)
        self.assertEqual([item.number for item, _ in plan], [1, 2])

    def test_failed_newer_preparation_has_no_authority_and_closes_nothing(self) -> None:
        eligible = self.eligible(pr(1, "v1.0.0"))
        self.assertEqual(
            supersession.plan_supersession(eligible, base_version="v0.9.0", authoritative_version=None), []
        )

    def test_older_request_cannot_close_newer_rollout(self) -> None:
        eligible = self.eligible(pr(1, "v1.0.0"), pr(2, "v1.2.0"))
        plan = supersession.plan_supersession(
            eligible, base_version="v0.9.0", authoritative_version="v1.0.0", authoritative_pr=1
        )
        self.assertEqual(plan, [])

    def test_dry_run_reconcile_performs_zero_mutations(self) -> None:
        registry = ROOT / "managed-projects.json"
        with patch.object(supersession, "list_open_prs", return_value=[pr(1, "v1.0.0", repository="lehard/planner-agent-lab"), pr(2, "v1.1.0", repository="lehard/planner-agent-lab")]), \
             patch.object(supersession, "committed_platform_version", return_value="v1.0.0"), \
             patch.object(supersession, "close_and_delete") as close:
            report = supersession.reconcile(
                repository="lehard/planner-agent-lab", base_branch="main", expected_bot="dev-platform-bot[bot]",
                registry=registry, authoritative_version=None, authoritative_pr=None, apply=False,
            )
        self.assertEqual([item["number"] for item in report["planned_closures"]], [1])
        self.assertEqual((report["authoritative_version"], report["authoritative_pr"]), ("v1.1.0", 2))
        close.assert_not_called()

    def test_maintenance_uses_newest_eligible_pr_and_preserves_it(self) -> None:
        registry = ROOT / "managed-projects.json"
        with patch.object(supersession, "list_open_prs", return_value=[
            pr(1, "v1.4.17", repository="lehard/planner-agent-lab"),
            pr(2, "v1.4.18", repository="lehard/planner-agent-lab"),
            pr(3, "v1.4.20", repository="lehard/planner-agent-lab"),
        ]), patch.object(supersession, "committed_platform_version", return_value="v1.4.16"):
            report = supersession.reconcile(
                repository="lehard/planner-agent-lab", base_branch="main", expected_bot="dev-platform-bot[bot]",
                registry=registry, authoritative_version=None, authoritative_pr=None, apply=False,
            )
        self.assertEqual([item["number"] for item in report["planned_closures"]], [1, 2])
        self.assertEqual((report["authoritative_version"], report["authoritative_pr"]), ("v1.4.20", 3))

    def test_candidate_and_excluded_repositories_cannot_enter_reconciliation(self) -> None:
        for repository in ("lehard/etsy", "lehard/lection"):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                supersession.require_managed(repository, ROOT / "managed-projects.json")

    def test_branch_delete_failure_is_warning_only_after_confirmed_close(self) -> None:
        responses = iter([{}, {"state": "closed"}, {}, ValueError("protected branch")])
        with patch.object(supersession, "gh_api", side_effect=lambda *_args, **_kwargs: next(responses)):
            supersession.close_and_delete(
                "lehard/managed", supersession.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0"),
                "committed downstream base already uses v1.0.0",
            )

    def test_successful_empty_delete_response_is_not_an_api_failure(self) -> None:
        completed = supersession.subprocess.CompletedProcess(["gh"], 0, "", "")
        self.assertIsNone(supersession.gh_api(["-X", "DELETE", "repos/lehard/managed/git/refs/heads/x"], runner=lambda *_args, **_kwargs: completed))


class RolloutSupersessionWorkflowTests(unittest.TestCase):
    def test_normal_rollout_reconciles_only_after_target_pr_is_confirmed(self) -> None:
        workflow = (ROOT / ".github/workflows/rollout.yml").read_text(encoding="utf-8")
        self.assertIn("Supersede older validated rollout PRs", workflow)
        self.assertIn("python3 scripts/rollout_supersession.py", workflow)
        self.assertIn("--authoritative-pr \"$TARGET_PR\"", workflow)
        self.assertIn("${APP_SLUG}[bot]", workflow)
        self.assertIn("dev-platform-managed-rollout: validated-exact-version", workflow)
        self.assertNotIn("--force", workflow.lower())

    def test_maintenance_is_explicit_dry_run_or_confirmed_apply_and_uses_managed_matrix(self) -> None:
        workflow = (ROOT / ".github/workflows/reconcile-stale-rollouts.yml").read_text(encoding="utf-8")
        self.assertIn("options: [dry-run, apply]", workflow)
        self.assertIn("confirm_apply=SUPERSEDE_STALE_ROLLOUTS", workflow)
        self.assertIn("scripts/managed_projects.py matrix", workflow)
        self.assertIn("if [[ \"$MODE\" == apply ]]; then args+=(--apply); fi", workflow)
        self.assertIn("actions/create-github-app-token@", workflow)


if __name__ == "__main__":
    unittest.main()
