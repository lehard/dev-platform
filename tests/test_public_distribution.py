from __future__ import annotations

import importlib.util
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_distribution_test", ROOT / "scripts" / "public_distribution.py")
assert SPEC and SPEC.loader
public_distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(public_distribution)


def _git_track(root: Path) -> None:
    """Initialize `root` as a Git checkout and stage everything currently in it.

    `git ls-files` reads the index, so `git add` (no commit, no identity
    config) is enough to make files visible as tracked source.
    """
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


class PublicDistributionTests(unittest.TestCase):
    def test_shipped_sanitizer_has_no_built_in_compatibility_marker_denylist(self) -> None:
        # Private-project compatibility deny data is one-shot cutover input,
        # never shipped source -- see design.md decision 6. `CANONICAL_PRODUCT_REPOSITORIES`
        # is limited to this repository's own canonical identity, with no
        # companion operator repository baked in.
        self.assertFalse(hasattr(public_distribution, "COMPATIBILITY_MARKERS"))
        self.assertEqual(
            public_distribution.CANONICAL_PRODUCT_REPOSITORIES, {public_distribution.CANONICAL_PRODUCT_REPOSITORY}
        )

    def test_audit_and_snapshot_use_the_same_candidate_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "safe.txt").write_text("safe fixture\n", encoding="utf-8")
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))
            result = public_distribution.snapshot(root, root / "snapshot.tar")
            self.assertEqual(result["audit"]["candidate_files"], receipt["candidate_files"])

    def test_tests_and_accepted_specs_are_required_source_and_stay_in_the_candidate_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_example.py").write_text("def test_ok(): pass\n", encoding="utf-8")
            specs = root / "openspec" / "specs" / "example" / "spec.md"
            specs.parent.mkdir(parents=True)
            specs.write_text("# Example spec\n", encoding="utf-8")
            _git_track(root)
            candidates = public_distribution.public_files(root)
            relative = {path.relative_to(root).as_posix() for path in candidates}
            self.assertIn("tests/test_example.py", relative)
            self.assertIn("openspec/specs/example/spec.md", relative)

    def test_openspec_changes_archive_is_excluded_as_maintenance_only_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            archived = root / "openspec" / "changes" / "archive" / "2020-01-01-old-change" / "proposal.md"
            archived.parent.mkdir(parents=True)
            archived.write_text("# Old change\n", encoding="utf-8")
            _git_track(root)
            candidates = public_distribution.public_files(root)
            relative = {path.relative_to(root).as_posix() for path in candidates}
            self.assertNotIn(
                "openspec/changes/archive/2020-01-01-old-change/proposal.md", relative
            )

    def test_cutover_policy_marker_blocks_audit_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as policy_tmp, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "notes.md").write_text(
                "Published by SyntheticPartnerCo protected-main agent lifecycle.\n", encoding="utf-8"
            )
            _git_track(root)
            policy_path = Path(policy_tmp) / "cutover-policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "compatibility_markers": {"legacy_merge_partner": r"\bSyntheticPartnerCo\b"},
                    }
                ),
                encoding="utf-8",
            )
            receipt = public_distribution.audit_tree(root, cutover_policy_path=policy_path)
            self.assertTrue(public_distribution.has_findings(receipt))
            self.assertTrue(receipt["findings"]["compatibility_markers"])
            self.assertNotIn("SyntheticPartnerCo", json.dumps(receipt))
            with self.assertRaises(ValueError):
                public_distribution.snapshot(root, root / "snapshot.tar", cutover_policy_path=policy_path)

    def test_cutover_policy_prohibited_repository_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as policy_tmp, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "notes.md").write_text("See acme/legacy-service for details.\n", encoding="utf-8")
            _git_track(root)
            policy_path = Path(policy_tmp) / "cutover-policy.json"
            policy_path.write_text(
                json.dumps({"version": 1, "prohibited_repositories": {"legacy_downstream": "acme/legacy-service"}}),
                encoding="utf-8",
            )
            receipt = public_distribution.audit_tree(root, cutover_policy_path=policy_path)
            self.assertTrue(public_distribution.has_findings(receipt))
            self.assertTrue(receipt["findings"]["operator_state"])
            self.assertNotIn("acme/legacy-service", json.dumps(receipt))

    def test_cutover_policy_receipt_records_provenance_without_deny_values(self) -> None:
        with tempfile.TemporaryDirectory() as policy_tmp, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            _git_track(root)
            policy_path = Path(policy_tmp) / "cutover-policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "prohibited_repositories": {"legacy_downstream": "acme/legacy-service"},
                        "compatibility_markers": {"legacy_merge_partner": r"\bSyntheticPartnerCo\b"},
                    }
                ),
                encoding="utf-8",
            )
            receipt = public_distribution.audit_tree(root, cutover_policy_path=policy_path)
            provenance = receipt["policy"]["cutover_policy"]
            self.assertEqual(provenance["path_basename"], "cutover-policy.json")
            self.assertEqual(provenance["version"], 1)
            self.assertTrue(provenance["digest"])
            self.assertNotIn("acme/legacy-service", json.dumps(receipt))
            self.assertNotIn("SyntheticPartnerCo", json.dumps(receipt))

    def test_cutover_policy_missing_or_malformed_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as policy_tmp, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            _git_track(root)
            missing_path = Path(policy_tmp) / "does-not-exist.json"
            with self.assertRaises(public_distribution.CutoverPolicyError):
                public_distribution.audit_tree(root, cutover_policy_path=missing_path)

            not_json = Path(policy_tmp) / "not-json.json"
            not_json.write_text("not json", encoding="utf-8")
            with self.assertRaises(public_distribution.CutoverPolicyError):
                public_distribution.audit_tree(root, cutover_policy_path=not_json)

            bad_version = Path(policy_tmp) / "bad-version.json"
            bad_version.write_text(json.dumps({"version": 2}), encoding="utf-8")
            with self.assertRaises(public_distribution.CutoverPolicyError):
                public_distribution.audit_tree(root, cutover_policy_path=bad_version)

            bad_marker = Path(policy_tmp) / "bad-marker.json"
            bad_marker.write_text(
                json.dumps({"version": 1, "compatibility_markers": {"Not A Label": "x"}}), encoding="utf-8"
            )
            with self.assertRaises(public_distribution.CutoverPolicyError):
                public_distribution.audit_tree(root, cutover_policy_path=bad_marker)

            bad_repo_shape = Path(policy_tmp) / "bad-repo.json"
            bad_repo_shape.write_text(
                json.dumps({"version": 1, "prohibited_repositories": {"legacy_downstream": "not-owner-shaped"}}),
                encoding="utf-8",
            )
            with self.assertRaises(public_distribution.CutoverPolicyError):
                public_distribution.audit_tree(root, cutover_policy_path=bad_repo_shape)

            with self.assertRaises(ValueError):
                public_distribution.snapshot(root, root / "snapshot.tar", cutover_policy_path=missing_path)

    def test_cutover_policy_file_is_excluded_from_candidate_set_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            policy_path = root / "cutover-policy.json"
            policy_path.write_text(json.dumps({"version": 1}), encoding="utf-8")
            # Track the policy file too, so this proves the explicit
            # `policy_extra_excluded` exclusion -- not merely that an
            # untracked file is invisible to the Git-tracked candidate source.
            _git_track(root)
            receipt = public_distribution.audit_tree(root, cutover_policy_path=policy_path)
            self.assertNotIn("cutover-policy.json", receipt["candidate_files"])
            self.assertFalse(public_distribution.has_findings(receipt))
            result = public_distribution.snapshot(root, root / "snapshot.tar", cutover_policy_path=policy_path)
            self.assertNotIn("cutover-policy.json", result["audit"]["candidate_files"])

    def test_missing_required_path_referenced_by_readme_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "See [scripts/does_not_exist.py](scripts/does_not_exist.py) for details.\n",
                encoding="utf-8",
            )
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertTrue(public_distribution.has_findings(receipt))
            self.assertTrue(receipt["findings"]["missing_required_paths"])

    def test_missing_required_path_referenced_by_ci_workflow_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text(
                "steps:\n  - run: python3 scripts/does_not_exist.py\n", encoding="utf-8"
            )
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertTrue(public_distribution.has_findings(receipt))
            self.assertTrue(receipt["findings"]["missing_required_paths"])

    def test_canonical_identity_and_synthetic_examples_are_not_compatibility_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "notes.md").write_text(
                "Canonical: lehard/dev-platform. Synthetic fixtures use "
                "example-org/legacy-merge-harness and example-org/legacy-publish-harness.\n",
                encoding="utf-8",
            )
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))

    def test_present_required_paths_do_not_block_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "See [tests/](tests/) and [scripts/present.py](scripts/present.py).\n",
                encoding="utf-8",
            )
            (root / "scripts").mkdir()
            (root / "scripts" / "present.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_present.py").write_text("def test_ok(): pass\n", encoding="utf-8")
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))

    def test_installation_state_and_nested_cache_are_not_product_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / ".dev-platform.toml").write_text("lehard" + "/private-operator\n", encoding="utf-8")
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "helper.cpython-313.pyc").write_bytes(b"machine-local")
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))
            self.assertEqual(receipt["candidate_files"], ["README.md"])

    def test_shared_requirement_integration_manifest_is_omitted_from_audit_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            manifest = root / "dev-platform" / "requirement-integrations" / "requirement-207.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"source_issue": "lehard' + '/development-backlog#207"}\n', encoding="utf-8")
            _git_track(root)

            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))
            self.assertNotIn("dev-platform/requirement-integrations/requirement-207.json", receipt["candidate_files"])

            public_distribution.snapshot(root, root / "snapshot.tar")
            with tarfile.open(root / "snapshot.tar") as archive:
                self.assertNotIn("dev-platform/requirement-integrations/requirement-207.json", archive.getnames())

    def test_noncanonical_owner_reference_in_product_file_still_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_file = root / "docs" / "product.md"
            product_file.parent.mkdir(parents=True)
            product_file.write_text("See lehard" + "/development-backlog#207.\n", encoding="utf-8")
            _git_track(root)

            receipt = public_distribution.audit_tree(root)
            self.assertTrue(public_distribution.has_findings(receipt))
            self.assertIn("docs/product.md", receipt["candidate_files"])
            self.assertTrue(receipt["findings"]["operator_state"])
            with self.assertRaises(ValueError):
                public_distribution.snapshot(root, root / "snapshot.tar")

    def test_packaged_owner_reference_blocks_audit_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "operator.md").write_text("lehard" + "/private-project\n", encoding="utf-8")
            _git_track(root)
            receipt = public_distribution.audit_tree(root)
            self.assertTrue(public_distribution.has_findings(receipt))
            with self.assertRaises(ValueError):
                public_distribution.snapshot(root, root / "snapshot.tar")

    def test_untracked_local_file_is_excluded_from_candidate_set_digest_and_findings(self) -> None:
        # Regression for a live cutover finding: an untracked local audit note
        # (never `git add`ed, listed in `.git/info/exclude`) must never become
        # public-distribution candidate source, must never move the candidate
        # digest, and must never produce a finding -- see proposal.md.
        with tempfile.TemporaryDirectory() as policy_tmp, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            _git_track(root)
            baseline_receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(baseline_receipt))
            baseline_digest = baseline_receipt["candidate_sha256"]

            policy_path = Path(policy_tmp) / "cutover-policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "prohibited_repositories": {"legacy_downstream": "acme/legacy-service"},
                        "compatibility_markers": {"legacy_merge_partner": r"\bSyntheticPartnerCo\b"},
                    }
                ),
                encoding="utf-8",
            )

            local_only = root / ".local" / "audits" / "PRIVATE_AUDIT.md"
            local_only.parent.mkdir(parents=True)
            local_only.write_text(
                "Published by SyntheticPartnerCo. See acme/legacy-service.\n", encoding="utf-8"
            )
            # Deliberately not `git add`ed: this simulates an untracked
            # working-tree scratch file that was never repository source.

            receipt = public_distribution.audit_tree(root, cutover_policy_path=policy_path)
            self.assertFalse(public_distribution.has_findings(receipt))
            self.assertNotIn(".local/audits/PRIVATE_AUDIT.md", receipt["candidate_files"])
            self.assertEqual(receipt["candidate_sha256"], baseline_digest)

            result = public_distribution.snapshot(root, root / "snapshot.tar", cutover_policy_path=policy_path)
            with tarfile.open(root / "snapshot.tar") as archive:
                self.assertNotIn(".local/audits/PRIVATE_AUDIT.md", archive.getnames())
            self.assertEqual(result["sha256"], baseline_digest)

    def test_tracked_file_with_same_marker_still_blocks_audit(self) -> None:
        # The fix is scoped to the candidate *source*, not the exclusion
        # policy: the same private material committed as tracked source must
        # still block the public snapshot exactly as before.
        with tempfile.TemporaryDirectory() as policy_tmp, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / ".local").mkdir()
            tracked = root / ".local" / "committed-by-mistake.md"
            tracked.write_text("Published by SyntheticPartnerCo. See acme/legacy-service.\n", encoding="utf-8")
            _git_track(root)

            policy_path = Path(policy_tmp) / "cutover-policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "prohibited_repositories": {"legacy_downstream": "acme/legacy-service"},
                        "compatibility_markers": {"legacy_merge_partner": r"\bSyntheticPartnerCo\b"},
                    }
                ),
                encoding="utf-8",
            )
            receipt = public_distribution.audit_tree(root, cutover_policy_path=policy_path)
            self.assertTrue(public_distribution.has_findings(receipt))
            self.assertIn(".local/committed-by-mistake.md", receipt["candidate_files"])
            self.assertTrue(receipt["findings"]["compatibility_markers"])
            self.assertTrue(receipt["findings"]["operator_state"])
            with self.assertRaises(ValueError):
                public_distribution.snapshot(root, root / "snapshot.tar", cutover_policy_path=policy_path)

    def test_public_files_fails_closed_outside_a_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            with self.assertRaises(public_distribution.GitSourceError):
                public_distribution.public_files(root)
            with self.assertRaises(public_distribution.GitSourceError):
                public_distribution.audit_tree(root)
            with self.assertRaises(public_distribution.GitSourceError):
                public_distribution.snapshot(root, root / "snapshot.tar")

    def test_history_audit_reports_fake_secret_without_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "credential.txt").write_text("ghp_" + "a" * 30, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "synthetic credential"], cwd=root, check=True)
            receipt = public_distribution.history_audit(root)
            self.assertEqual(receipt["findings"][0]["pattern"], "github_pat")
            self.assertNotIn("ghp_", str(receipt["findings"]))

    def test_history_audit_reads_blobs_in_bounded_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "safe.txt").write_text("safe\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "safe"], cwd=root, check=True)
            with mock.patch.object(public_distribution.subprocess, "run", wraps=subprocess.run) as run:
                receipt = public_distribution.history_audit(root)
            self.assertFalse(receipt["findings"])
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn(["git", "cat-file", "--batch"], commands)
            self.assertLessEqual(len(commands), 5)
