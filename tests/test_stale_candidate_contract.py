"""A disposable repository proves where each job kind reads its platform contract."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_common import read_platform_config  # noqa: E402
from _platform_modules import write_trusted_contract  # noqa: E402
import candidate_lifecycle as lifecycle  # noqa: E402
import lifecycle_workers as workers  # noqa: E402

CONTRACT = (ROOT / "dev-platform" / "source-contract.toml").read_text(encoding="utf-8")
MISSING_KEY = "main_branch"
STALE = "\n".join(line for line in CONTRACT.splitlines() if not line.startswith(f"{MISSING_KEY} ")) + "\n"
VALID_MARK = "# the candidate's own valid contract\n"
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@localhost", *args], cwd=cwd, check=True,
                          text=True, capture_output=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        git(self.source, "init", "-qb", "main")
        self.trusted = self.base / "trusted"
        write_trusted_contract(self.trusted)
        self.work = self.base / "work"
        self.work.mkdir()

    def commit(self, contract: str | None) -> str:
        path = self.source / "dev-platform/source-contract.toml"
        path.parent.mkdir(exist_ok=True)
        if contract is None:
            path.unlink(missing_ok=True)
            (self.source / "marker").write_text("no contract\n")
        else:
            path.write_text(contract)
        git(self.source, "add", "-A")
        git(self.source, "commit", "-qm", "candidate")
        return git(self.source, "rev-parse", "HEAD")

    def review(self, head: str, trusted: Path | None = None) -> dict:
        seen = {}

        def handler(checkout):
            seen["config"] = read_platform_config(checkout)
            seen["installed"] = (checkout / ".dev-platform.toml").read_text()
            return {"status": "reviewed"}

        job = {"kind": "review", "number": 7, "head": head, "attempt": 1, "task_identity": {"change": "c"}}
        workers.execute_job(job, source_repo=str(self.source), branch="b", allowed_paths=[], llm_command=[],
                            current_head=lambda: head, post_result=lambda _: None, workdir=str(self.work), worker="w",
                            review_handler=handler, trusted_root=trusted or self.trusted)
        return seen


class ReviewAndRepairContractTests(Base):
    def test_stale_candidate_review_reads_the_trusted_contract(self):
        seen = self.review(self.commit(STALE))
        self.assertEqual(seen["config"][MISSING_KEY], "main")

    def test_valid_candidate_review_still_receives_the_trusted_contract(self):
        seen = self.review(self.commit(VALID_MARK + CONTRACT))
        self.assertNotIn(VALID_MARK, seen["installed"])
        self.assertEqual(seen["installed"], CONTRACT)

    def test_a_missing_trusted_contract_fails_naming_the_file(self):
        head = self.commit(CONTRACT)
        empty = self.base / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(workers.WorkerError, "trusted platform contract .*source-contract.toml is missing"):
            self.review(head, empty)

    def test_a_job_without_a_trusted_root_fails(self):
        head = self.commit(CONTRACT)
        job = {"kind": "review", "number": 7, "head": head, "attempt": 1, "task_identity": {"change": "c"}}
        with self.assertRaisesRegex(workers.WorkerError, "needs the trusted default-branch checkout"):
            workers.execute_job(job, source_repo=str(self.source), branch="b", allowed_paths=[], llm_command=[],
                                current_head=lambda: head, post_result=lambda _: None, workdir=str(self.work), worker="w")

    def test_repair_harness_receives_the_trusted_contract(self):
        head = self.commit(STALE)
        harness = self.base / "harness"
        git(self.base, "clone", "-q", "--no-checkout", str(self.source), str(harness))
        workers.checkout_harness(harness, head, self.trusted / workers.SOURCE_CONTRACT)
        self.assertEqual(read_platform_config(harness)[MISSING_KEY], "main")


class IntegrationHarnessContractTests(Base):
    def harness(self, head: str) -> Path:
        harness = self.base / "harness"
        git(self.base, "clone", "-q", "--no-checkout", str(self.source), str(harness))
        workers.checkout_harness(harness, head)
        return harness

    def test_the_stale_copy_is_replaced_by_the_merged_head_contract(self):
        harness = self.harness(self.commit(STALE))
        with self.assertRaisesRegex(RuntimeError, f"missing required key {MISSING_KEY}"):
            read_platform_config(harness)
        merged = self.commit(CONTRACT)
        git(harness, "fetch", "-q", "origin")
        workers.checkout_harness(harness, merged)
        self.assertEqual(read_platform_config(harness)[MISSING_KEY], "main")
        self.assertEqual(git(harness, "status", "--porcelain"), "")
        exclude = (harness / ".git/info/exclude").read_text().splitlines()
        self.assertEqual(exclude.count(".dev-platform.toml"), 1)

    def test_a_committed_project_contract_is_never_touched(self):
        (self.source / ".dev-platform.toml").write_text(VALID_MARK + CONTRACT)
        head = self.commit(STALE)
        harness = self.harness(head)
        workers.checkout_harness(harness, head, self.trusted / workers.SOURCE_CONTRACT)
        self.assertEqual((harness / ".dev-platform.toml").read_text(), VALID_MARK + CONTRACT)
        self.assertEqual(git(harness, "status", "--porcelain"), "")

    def test_a_head_without_a_contract_fails_naming_the_file(self):
        with self.assertRaisesRegex(workers.WorkerError, "dev-platform/source-contract.toml; no platform contract"):
            self.harness(self.commit(None))

    def test_a_head_that_lost_its_contract_does_not_keep_the_old_copy(self):
        harness = self.harness(self.commit(CONTRACT))
        gone = self.commit(None)
        git(harness, "fetch", "-q", "origin")
        with self.assertRaisesRegex(workers.WorkerError, "dev-platform/source-contract.toml; no platform contract"):
            workers.checkout_harness(harness, gone)


class FinalizeContractTests(Base):
    def gate(self, refused: list[dict]):
        return workers.finalize_contract_gate(str(self.source), workdir=str(self.work), refused=refused)

    def job(self, head: str, identity=None) -> dict:
        return {"kind": "finalize", "number": 7, "head": head, "attempt": 0, "task_identity": identity or {"change": "c"}}

    def test_missing_key_refuses_naming_the_key_and_the_exit(self):
        refused: list[dict] = []
        head = self.commit(STALE)
        self.assertFalse(self.gate(refused)(self.job(head)))
        self.assertEqual((refused[0]["number"], refused[0]["kind"]), (7, "finalize"))
        self.assertIn(f"missing required key {MISSING_KEY}", refused[0]["error"])
        self.assertIn("reconcile the candidate with main and run finish", refused[0]["error"])
        self.assertNotIn(str(self.work), refused[0]["error"])

    def test_composition_finalize_is_refused_the_same_way(self):
        refused: list[dict] = []
        head = self.commit(STALE)
        identity = {"kind": "requirement-composition", "requirement": "o/r#1"}
        self.assertFalse(self.gate(refused)(self.job(head, identity)))
        self.assertIn(MISSING_KEY, refused[0]["error"])

    def test_unreadable_contracts_refuse(self):
        for contract, expected in (("not = [valid toml\n", "invalid or unreadable"), (None, "no platform contract")):
            with self.subTest(expected=expected):
                refused: list[dict] = []
                self.assertFalse(self.gate(refused)(self.job(self.commit(contract))))
                self.assertIn(expected, refused[0]["error"])

    def test_refusal_posts_no_claim_and_spends_nothing(self):
        head = self.commit(STALE)
        job = workers.job_record("finalize", head, {"change": "c"}, 0)
        record = lifecycle.build_handoff_record(
            number=7, state="finalize-pending", head=head, task_identity={"change": "c"}, gates={}, red_gate=None,
            not_reverified=[], attempts={}, next_job=job, at="2026-11-06T00:00:00Z", route=None)
        handoff = {"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}
        posted, refused = [], []
        gate = self.gate(refused)
        result = workers.work_next(frozenset({"finalize"}), list_prs=lambda: [{"number": 7, "head": {"sha": head}, "state": "open"}],
                                   comments_for=lambda _: [handoff], post_comment=lambda _, body: posted.append(body),
                                   worker="w", now=NOW, eligible=gate)
        self.assertEqual((result["status"], posted), ("idle", []))
        self.assertEqual(len(refused), 1)
        built = {**job, "number": 7}
        self.assertEqual(workers.release_count(built, [handoff]), 0)
        self.assertEqual(workers.environment_release_count(built, [handoff]), 0)

    def test_the_exit_head_passes_the_gate(self):
        refused: list[dict] = []
        self.assertFalse(self.gate(refused)(self.job(self.commit(STALE))))
        self.assertTrue(self.gate(refused)(self.job(self.commit(CONTRACT))))
        self.assertEqual(len(refused), 1)

    def test_other_kinds_are_not_inspected(self):
        refused: list[dict] = []
        self.assertTrue(self.gate(refused)({"kind": "review", "number": 7, "head": "f" * 40}))
        self.assertEqual(refused, [])


if __name__ == "__main__":
    unittest.main()
