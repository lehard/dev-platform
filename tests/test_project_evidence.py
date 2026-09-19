"""Deterministic contract coverage for Project Evidence Snapshots."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "template" / "scripts" / "project_evidence.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("project_evidence", SCRIPT)
assert SPEC and SPEC.loader
project_evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_evidence
SPEC.loader.exec_module(project_evidence)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def init_repo() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    for relative, content in {
        "README.md": "# Example\n",
        "AGENTS.md": "# Rules\n",
        "docs/engineering/project-rules.md": "# Engineering rules\n",
        "docs/context/domain.md": "# Domain\n",
        "openspec/specs/payments/spec.md": "# Payments\n",
        "src/payments.py": "def pay(): pass\n",
        "unrelated.bin": "never inventory this\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "seed")
    return temporary


def results_for(root: Path, *, confidence: str = "high", conflicts: list[str] | None = None) -> dict[str, dict]:
    current = project_evidence.inventory(root)
    results: dict[str, dict] = {}
    for concern, dependencies in current["dependencies"].items():
        facts = [] if not dependencies else [{"statement": f"{concern} fact", "evidence_refs": [dependencies[0]]}]
        results[concern] = {
            "version": 1,
            "confidence": confidence,
            "facts": facts,
            "conflicts": conflicts or [],
            "unknowns": [],
            "provenance_ref": f"routing:{concern}",
            "usage": {"model_calls": 1},
        }
    return results


class ProjectEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = init_repo()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_first_build_records_git_blob_sources_and_read_only_worker_contract(self) -> None:
        snapshot, evidence = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        self.assertEqual(snapshot["version"], 1)
        self.assertTrue(all(source["identity"]["algorithm"] == "git-blob" for source in snapshot["sources"]))
        self.assertEqual(evidence["rebuild"], len(project_evidence.CONCERNS))
        self.assertEqual(evidence["routine_worker_count"], len(project_evidence.CONCERNS))
        self.assertEqual(evidence["model_calls"], len(project_evidence.CONCERNS))
        self.assertEqual(project_evidence.validate_snapshot(self.root, snapshot), {
            "ok": True,
            "freshness": "fresh",
            "changed_sources": [],
            "digest": snapshot["digest"],
        })
        pending, _ = project_evidence.build_snapshot(self.root, prior=None, results={})
        request = pending["projections"]["project-context"]["worker_request"]
        self.assertEqual(request["result_contract"]["write_authority"], "none")
        self.assertTrue(request["result_contract"]["non_authoritative"])
        self.assertIn("raw transcripts", request["result_contract"]["forbidden"])

    def test_unchanged_snapshot_hits_without_worker_work(self) -> None:
        first, _ = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        second, evidence = project_evidence.build_snapshot(self.root, prior=first, results={})
        self.assertEqual(evidence["hit"], len(project_evidence.CONCERNS))
        self.assertEqual(evidence["rebuild"], 0)
        self.assertEqual(evidence["routine_worker_count"], 0)
        self.assertEqual(evidence["model_calls"], 0)
        self.assertEqual(first["projections"], second["projections"])
        self.assertEqual(first["digest"], second["digest"])

    def test_context_change_rebuilds_only_its_dependency_closure(self) -> None:
        first, _ = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        (self.root / "docs/context/domain.md").write_text("# Changed domain\n", encoding="utf-8")
        second, evidence = project_evidence.build_snapshot(self.root, prior=first, results={})
        self.assertEqual(evidence["hit"], 4)
        self.assertEqual(evidence["rebuild"], 2)
        self.assertEqual(second["projections"]["project-context"]["status"], "requires-extraction")
        self.assertEqual(second["projections"]["conflicts-unknowns"]["status"], "requires-extraction")
        self.assertEqual(second["projections"]["accepted-system"], first["projections"]["accepted-system"])

    def test_changes_covering_every_concern_force_full_rebuild(self) -> None:
        first, _ = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        for relative in (
            "openspec/specs/payments/spec.md",
            "src/payments.py",
            "docs/engineering/project-rules.md",
            "docs/context/domain.md",
        ):
            path = self.root / relative
            path.write_text(path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
        _, evidence = project_evidence.build_snapshot(self.root, prior=first, results={})
        self.assertEqual(evidence["hit"], 0)
        self.assertEqual(evidence["rebuild"], len(project_evidence.CONCERNS))

    def test_revision_staleness_is_exposed_but_unchanged_dependencies_reuse(self) -> None:
        first, _ = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        git(self.root, "commit", "--allow-empty", "-q", "-m", "revision only")
        report = project_evidence.validate_snapshot(self.root, first)
        self.assertEqual(report["freshness"], "stale-revision")
        _, evidence = project_evidence.build_snapshot(self.root, prior=first, results={})
        self.assertEqual(evidence["hit"], len(project_evidence.CONCERNS))

    def test_conflict_or_low_confidence_never_promotes_fresh_projection(self) -> None:
        supplied = results_for(self.root, confidence="low", conflicts=["Accepted spec and context disagree."])
        snapshot, evidence = project_evidence.build_snapshot(self.root, prior=None, results=supplied)
        self.assertEqual(evidence["escalation_count"], len(project_evidence.CONCERNS))
        for projection in snapshot["projections"].values():
            self.assertEqual(projection["status"], "escalation-required")
            self.assertIn(projection["escalation_reason"], ("conflicting evidence", "low confidence"))
        project_evidence.validate_snapshot(self.root, snapshot)

    def test_missing_worker_usage_stays_unknown_not_a_zero_guess(self) -> None:
        supplied = results_for(self.root)
        del supplied["rules"]["usage"]
        _, evidence = project_evidence.build_snapshot(self.root, prior=None, results=supplied)
        self.assertEqual(evidence["routine_worker_count"], len(project_evidence.CONCERNS))
        self.assertIsNone(evidence["model_calls"])

    def test_unlinked_worker_fact_and_digest_tampering_are_rejected(self) -> None:
        bad = results_for(self.root)
        bad["project-context"]["facts"] = [{"statement": "unsupported", "evidence_refs": ["not-in-snapshot.md"]}]
        with self.assertRaisesRegex(project_evidence.ProjectEvidenceError, "unlinked evidence_refs"):
            project_evidence.build_snapshot(self.root, prior=None, results=bad)
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        snapshot["projections"]["rules"]["digest"] = "0" * 64
        with self.assertRaisesRegex(project_evidence.ProjectEvidenceError, "projection rules digest"):
            project_evidence.validate_snapshot(self.root, snapshot, check_freshness=False)

    def test_inventory_does_not_read_unrelated_files(self) -> None:
        original = project_evidence._identity
        observed: list[str] = []

        def recording(root: Path, path: Path) -> dict[str, str]:
            observed.append(path.relative_to(root).as_posix())
            return original(root, path)

        with patch.object(project_evidence, "_identity", side_effect=recording):
            project_evidence.inventory(self.root)
        self.assertNotIn("unrelated.bin", observed)

    def test_instruction_inventory_uses_git_pathspec_instead_of_tree_walk(self) -> None:
        with patch.object(Path, "rglob", side_effect=AssertionError("unexpected repository walk")):
            paths = project_evidence._module_agents(self.root)
        self.assertEqual([path.relative_to(self.root).as_posix() for path in paths], ["AGENTS.md"])

    def test_cli_writes_and_binds_consumer_reference_to_digests(self) -> None:
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results=results_for(self.root))
        path = self.root / "snapshot.json"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        command = [
            sys.executable, str(SCRIPT), "--root", str(self.root), "reference", str(path),
            "--concern", "project-context", "--require-fresh",
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=True)
        reference = json.loads(result.stdout)
        self.assertEqual(reference["snapshot_digest"], snapshot["digest"])
        self.assertEqual(reference["projection_digest"], snapshot["projections"]["project-context"]["digest"])
        self.assertEqual(reference["projection_status"], "fresh")


if __name__ == "__main__":
    unittest.main()
