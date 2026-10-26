"""One task branch, one answer: the managed gate, the quick-task gate, publication and the agent board agree (BR-774/BR-777).

Each scenario builds a real branch against a bare origin and asks every consumer of the
task-base classification about it. Owner requirement: a managed task, a quick task, the publish
step and the board give the same answer for the same branch.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import _platform_common  # noqa: E402
import agent_board  # noqa: E402
import finish_task  # noqa: E402
import managed_task  # noqa: E402
import publication_queue  # noqa: E402


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True,
                          stdin=subprocess.DEVNULL).stdout.strip()


def configure(path: Path) -> None:
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")


CONTRACT = ('platform_version = "1.0.0"\nmain_branch = "main"\nworkflow_profile = "multi-agent"\n'
            'harness_mode = "platform"\n\n[capabilities]\nagent_board = true\n\n'
            '[paths]\nworktrees = ".claude/worktrees"\nagent_board = ".claude/agents-board.json"\n'
            'checks = "dev-platform/checks.toml"\n')


class TaskBaseMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.remote = base / "origin.git"
        seed = base / "seed"
        seed.mkdir()
        git(seed, "init", "-q", "-b", "main")
        configure(seed)
        (seed / ".gitignore").write_text(".claude/\n")
        (seed / ".dev-platform.toml").write_text(CONTRACT)
        (seed / "dev-platform").mkdir()
        (seed / "dev-platform/checks.toml").write_text("# no generated files\n")
        (seed / "shared.txt").write_text("".join(f"{n}\n" for n in ("a", "b", "c", "d", "e", "f", "g")))
        (seed / "conflict.txt").write_text("one\ntwo\nthree\n")
        git(seed, "add", "-A")
        git(seed, "commit", "-qm", "base")
        git(base, "clone", "-q", "--bare", str(seed), str(self.remote))
        self.root = base / "repo"
        git(base, "clone", "-q", str(self.remote), str(self.root))
        configure(self.root)
        self.task = self.worktree("task")
        self.sibling = self.worktree("sibling")
        self.other = base / "other"
        git(base, "clone", "-q", str(self.remote), str(self.other))
        configure(self.other)

    def worktree(self, name: str) -> Path:
        path = self.root / ".claude/worktrees" / name
        git(self.root, "worktree", "add", "-q", "-b", f"agent/{name}", str(path), "origin/main")
        configure(path)
        return path

    def commit(self, path: Path, files: dict[str, str], message: str) -> None:
        for name, text in files.items():
            (path / name).write_text(text)
        git(path, "add", "-A")
        git(path, "commit", "-qm", message)

    def land_on_main(self, files: dict[str, str]) -> None:
        git(self.other, "pull", "-q", "--ff-only")
        self.commit(self.other, files, "main advances")
        git(self.other, "push", "-q", "origin", "HEAD:main")
        git(self.root, "fetch", "-q", "origin")

    # ---- the consumers ------------------------------------------------------------------------

    def integrated(self, managed: bool) -> ExitStack:
        """queue_integrated's own inputs for a managed candidate or a quick task."""
        provenance = object() if managed else None
        stack = ExitStack()
        stack.enter_context(mock.patch.object(_platform_common, "lifecycle_mode", return_value="coordinator"))
        stack.enter_context(mock.patch.object(publication_queue, "enabled", return_value=True))
        stack.enter_context(mock.patch.object(managed_task, "resolve_canonical_provenance", return_value=provenance))
        stack.enter_context(mock.patch.object(_platform_common, "coordinator_candidate", return_value=managed))
        return stack

    def gate(self, *, managed: bool):
        """The fresh-base gate of validation as a managed candidate or a quick task sees it."""
        with self.integrated(managed):
            try:
                currency = _platform_common.require_handoff_task_base(self.task, "origin", "main")
            except _platform_common.TaskFreshnessError as exc:
                return ("reconcile-required", str(exc))
            return (currency.state, tuple(currency.overlapping))

    def publish(self, *, managed: bool):
        """The publish step's fresh-base gate (finish_task) for the same task kind: passes, or names why not."""
        with self.integrated(managed):
            try:
                finish_task.require_publication_task_base(self.task, "agent/task", "origin/main")
            except SystemExit as exc:
                return ("reconcile-required", str(exc))
            return ("publishes", None)

    def board(self) -> tuple[frozenset[str], list[str]]:
        board = self.root / ".claude/agents-board.json"
        board.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        items = [{"id": f"{name}-id", "task": f"{name} task", "scope": "", "branch": f"agent/{name}",
                  "worktree": str(path), "heartbeat": now} for name, path in (("task", self.task), ("sibling", self.sibling))]
        board.write_text(json.dumps({"version": 1, "items": items}))
        with mock.patch.object(agent_board, "board_path", return_value=board):
            conflicts = agent_board.hard_scope_conflicts(self.root, self.task, "agent/task")
        scope = frozenset(agent_board._factual_scope_paths(self.task, self.root, "main"))
        return scope, sorted(path for _, _, path in conflicts)

    def answer(self) -> dict:
        managed, quick = self.gate(managed=True), self.gate(managed=False)
        self.assertEqual(managed, quick, "a managed task and a quick task must get the same gate answer")
        for kind in (True, False):
            published = self.publish(managed=kind)[0]
            self.assertEqual(published == "publishes", managed[0] != "reconcile-required",
                             "the publish step must agree with the validation gate")
        scope, overlaps = self.board()
        main = git(self.task, "rev-parse", "origin/main")
        self.assertEqual(scope, _platform_common.task_own_paths(self.task, main),
                         "the board's task scope is the classifier's own task diff")
        return {"gate": managed[0], "overlapping": managed[1] if managed[0] != "reconcile-required" else None,
                "scope": scope, "overlaps": overlaps}

    # ---- the matrix ---------------------------------------------------------------------------

    def test_fresh_branch(self) -> None:
        self.commit(self.task, {"task.txt": "task\n"}, "task work")
        self.commit(self.sibling, {"sibling.txt": "sibling\n"}, "sibling work")
        self.assertEqual(self.answer(), {"gate": "fresh", "overlapping": (), "scope": {"task.txt"}, "overlaps": []})

    def test_behind_mergeable_with_files_from_main(self) -> None:
        self.commit(self.task, {"task.txt": "task\n"}, "task work")
        self.commit(self.sibling, {"sibling.txt": "sibling\n"}, "sibling work")
        self.land_on_main({"sibling.txt": "sibling\n"})  # the sibling's PR merged; its board entry is still active
        self.assertEqual(self.answer(), {"gate": "behind-mergeable", "overlapping": (), "scope": {"task.txt"}, "overlaps": []})
        git(self.task, "merge", "-q", "--no-edit", "origin/main")  # after reconcile: fresh, still no false overlap
        self.assertEqual(self.answer(), {"gate": "fresh", "overlapping": (), "scope": {"task.txt"}, "overlaps": []})

    def test_real_shared_file(self) -> None:
        lines = ["a", "b", "c", "d", "e", "f", "g"]
        def edited(index: int) -> str:
            return "".join(f"{line.upper() if i == index else line}\n" for i, line in enumerate(lines))
        self.commit(self.task, {"shared.txt": edited(0)}, "task edits shared")
        self.commit(self.sibling, {"shared.txt": edited(3)}, "sibling edits shared")
        self.land_on_main({"shared.txt": edited(6)})  # main changes a distant line: clean merge
        self.assertEqual(self.answer(), {"gate": "behind-mergeable", "overlapping": ("shared.txt",),
                                         "scope": {"shared.txt"}, "overlaps": ["shared.txt"]})

    def test_conflict(self) -> None:
        self.commit(self.task, {"conflict.txt": "task\ntwo\nthree\n"}, "task edits conflict")
        self.land_on_main({"conflict.txt": "main\ntwo\nthree\n"})
        answer = self.answer()
        self.assertEqual((answer["gate"], answer["scope"], answer["overlaps"]), ("reconcile-required", {"conflict.txt"}, []))
        self.assertIn("a trial merge conflicts in conflict.txt", self.gate(managed=False)[1])
        self.assertIn("a trial merge conflicts in conflict.txt", self.publish(managed=False)[1])


if __name__ == "__main__":
    unittest.main()
