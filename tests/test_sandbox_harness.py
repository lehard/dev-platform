"""The credential-free writer harness: process groups, disposable checkouts and result validation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template/scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from _concurrent_lifecycle import process_deadline_seconds  # noqa: E402
from _platform_modules import load_platform_module  # noqa: E402

harness = load_platform_module("sandbox_harness", ROOT / "template/scripts/sandbox_harness.py")


# A background child records its pid atomically, then sleeps far longer than any test before its late write.
LATE_CHILD = ("import os,sys,time; open(sys.argv[2]+'.tmp','w').write(str(os.getpid())); "
              "os.replace(sys.argv[2]+'.tmp',sys.argv[2]); time.sleep(600); open(sys.argv[1],'w').write('x')")


def assert_processes_gone(case: unittest.TestCase, pid_files: list[Path]) -> None:
    """Each recorded child must disappear within the bounded test deadline; a survivor is killed and named."""
    for pid_file in pid_files:
        case.assertTrue(pid_file.exists(), f"background child never recorded its pid in {pid_file}")
        pid = int(pid_file.read_text(encoding="utf-8"))
        deadline = time.monotonic() + process_deadline_seconds()
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() >= deadline:
                os.kill(pid, 9)
                case.fail(f"background child {pid} outlived its process group")
            time.sleep(0.05)


class EnvironmentTests(unittest.TestCase):
    def test_credentials_scrubbed(self):
        env = {"PATH": "/bin", "GH_TOKEN": "x", "GITHUB_TOKEN": "x", "GH_ENTERPRISE_TOKEN": "x",
               "GITHUB_ENTERPRISE_TOKEN": "x", "GIT_ASKPASS": "/a", "SSH_AUTH_SOCK": "/s",
               "MY_GITHUB_API_KEY": "x", "ANTHROPIC_API_KEY": "llm", "GIT_CONFIG_GLOBAL": "/home/.gitconfig"}
        clean = harness.credential_free_env(env)
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                     "GIT_ASKPASS", "SSH_AUTH_SOCK", "MY_GITHUB_API_KEY"):
            self.assertNotIn(name, clean)
        self.assertEqual(clean["ANTHROPIC_API_KEY"], "llm")
        self.assertEqual(clean["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(clean["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(clean["GIT_CONFIG_SYSTEM"], os.devnull)
        self.assertIn("GH_TOKEN", env)  # input untouched

    def test_llm_runs_with_scrubbed_env_and_devnull_stdin(self):
        seen = {}
        def runner(command, **kwargs):
            seen.update(kwargs, command=command)
            return subprocess.CompletedProcess(command, 0, "", "")
        harness.run_llm(["llm"], Path("/x"), tmp=Path("/w/llm-tmp"), env={"GH_TOKEN": "t", "PATH": "/bin"}, runner=runner)
        self.assertIs(seen["stdin"], subprocess.DEVNULL)
        self.assertNotIn("GH_TOKEN", seen["env"])
        self.assertEqual(seen["cwd"], Path("/x"))
        self.assertEqual([seen["env"][k] for k in ("TMPDIR", "TMP", "TEMP")], ["/w/llm-tmp"] * 3)
        with self.assertRaisesRegex(harness.WorkerError, "must kill its process group"):
            harness.run_llm(["llm"], Path("/x"), tmp=Path("/w/llm-tmp"), runner=subprocess.run)

    def test_run_in_session_kills_the_whole_group_after_the_leader_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker, held = Path(tmp) / "late", Path(tmp) / "held"
            pids = [Path(tmp) / "late.pid", Path(tmp) / "held.pid"]
            # one background child with closed pipes, one that keeps stdout open: neither outlives the leader,
            # which exits only once both children are live
            leader = ("import os,subprocess,sys,time; s=sys.argv[1]; "
                      "subprocess.Popen([sys.executable,'-c',s,sys.argv[2],sys.argv[4]],stdin=subprocess.DEVNULL,"
                      "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                      "subprocess.Popen([sys.executable,'-c',s,sys.argv[3],sys.argv[5]]); "
                      "[time.sleep(.01) for _ in iter(lambda: not all(map(os.path.exists, sys.argv[4:6])), False)]; "
                      "print('led')")
            # the stdout holder sleeps 600 s: had it kept run_in_session waiting, the bounded timeout would raise
            done = harness.run_in_session([sys.executable, "-c", leader, LATE_CHILD, str(marker), str(held), *map(str, pids)],
                                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                          timeout=process_deadline_seconds())
            self.assertEqual((done.returncode, done.stdout), (0, "led\n"))
            assert_processes_gone(self, pids)
            self.assertFalse(marker.exists())
            self.assertFalse(held.exists())

    def test_kill_process_group_accepts_a_group_of_only_zombies(self):
        # an unreaped exited leader keeps its group alive as a zombie; macOS answers killpg with EPERM
        process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        try:
            deadline = time.monotonic() + 10
            while harness.live_group_members(process.pid):
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)
            harness.kill_process_group(process.pid)
        finally:
            process.wait()
        harness.kill_process_group(process.pid)  # reaped: the group is gone

    def test_kill_process_group_refuses_eperm_while_a_live_member_remains(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        try:
            with mock.patch.object(harness.os, "killpg", side_effect=PermissionError(1, "Operation not permitted")):
                with self.assertRaisesRegex(harness.WorkerError, f"live members remain: {process.pid} "):
                    harness.kill_process_group(process.pid)
        finally:
            harness.kill_process_group(process.pid)
            process.wait()

    def test_run_in_session_timeout_kills_the_group(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            harness.run_in_session([sys.executable, "-c", "import time; time.sleep(30)"], capture_output=True,
                                   timeout=0.5, stdin=subprocess.DEVNULL)

    def test_scratch_home_hides_operator_github_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            real, work = Path(tmp) / "real", Path(tmp) / "work"
            (real / ".config" / "gh").mkdir(parents=True)
            (real / ".config" / "gh" / "hosts.yml").write_text("oauth_token: secret\n", encoding="utf-8")
            (real / ".codex").mkdir()
            (real / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
            home = harness.scratch_home(work, [".codex/auth.json"], source_home=real)
            self.assertTrue((home / ".codex" / "auth.json").is_file())
            self.assertFalse((home / ".config" / "gh" / "hosts.yml").exists())
            with self.assertRaises(harness.WorkerError):
                harness.scratch_home(work, [".config/gh/hosts.yml"], source_home=real)
            env = harness.credential_free_env({"HOME": str(real)}, home)
            self.assertEqual(env["HOME"], str(home))
            self.assertTrue(env["GH_CONFIG_DIR"].startswith(str(home)))

    def test_real_child_sees_no_credentials(self):
        code = "import os,json;print(json.dumps([k for k in os.environ if 'TOKEN' in k or k=='SSH_AUTH_SOCK']))"
        done = harness.run_llm([sys.executable, "-c", code], Path.cwd(), tmp=Path(tempfile.gettempdir()),
                               env={"PATH": os.environ.get("PATH", ""), "GH_TOKEN": "t", "SSH_AUTH_SOCK": "/s"})
        self.assertEqual(json.loads(done.stdout), [])


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    return subprocess.run(["git", *args], cwd=repo, env=env, text=True, capture_output=True, check=True).stdout.strip()


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        self.write("src/a.py", "1")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "remote", "add", "origin", self.repo.as_uri())

    def write(self, path, text):
        full = self.repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text)

    def commit(self, path):
        self.write(path, "changed")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "work")
        return git(self.repo, "rev-parse", "HEAD")

    def test_rejects_non_fast_forward(self):
        self.commit("src/a.py")
        git(self.repo, "checkout", "-q", "--detach", self.base)
        sibling = self.commit("src/b.py")
        other = self.base
        git(self.repo, "checkout", "-q", "--detach", self.base)
        diverged = self.commit("src/c.py")
        with self.assertRaisesRegex(harness.WorkerError, "fast-forward"):
            harness.validate_writer_result(self.repo, sibling, diverged)
        with self.assertRaises(harness.WorkerError):
            harness.validate_writer_result(self.repo, self.base, other)  # no new commits

    def test_accepts_a_fast_forward(self):
        result = self.commit("src/a.py")
        self.assertEqual(harness.validate_writer_result(self.repo, self.base, result), ["src/a.py"])

    def test_rejects_workflow_and_evidence_edits(self):
        cases = [(".github/workflows/ci.yml", "workflow"),
                 ("openspec/changes/c/verification.md", "evidence"), ("openspec/changes/c/automated-checks.json", "evidence"),
                 ("openspec/changes/c/independent-review-1.json", "evidence"),
                 ("openspec/changes/c/independent-reviews/r.json", "evidence"),
                 ("openspec/changes/c/evidence/test-result.json", "evidence"),
                 ("openspec/changes/c/nested/evidence/deep.json", "evidence")]
        for path, message in cases:
            with self.subTest(path=path):
                git(self.repo, "checkout", "-q", "--detach", self.base)
                result = self.commit(path)
                with self.assertRaisesRegex(harness.WorkerError, message):
                    harness.validate_writer_result(self.repo, self.base, result)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mark = Path(self.tmp.name) / "filter-ran"

    def test_tree_snapshot_hashes_directory_symlinks_and_refuses_special_files(self):
        root = Path(self.tmp.name) / "snap"
        (root / "d").mkdir(parents=True)
        first = harness.tree_snapshot(root)
        (root / "link").symlink_to(root / "d")
        self.assertNotEqual(harness.tree_snapshot(root), first)
        os.mkfifo(root / "d/pipe")
        with self.assertRaisesRegex(harness.WorkerError, "unsupported file type: d/pipe"):
            harness.tree_snapshot(root)

    def test_import_worktree_refuses_nested_git_metadata_before_copying(self):
        root = Path(self.tmp.name)
        src, dst = root / "ns", root / "nd"
        (src / ".git").mkdir(parents=True), (dst / ".git").mkdir(parents=True)
        (src / "a.txt").write_text("a")
        for nested in ("sub/.git", "sub/.GIT"):
            with self.subTest(nested=nested):
                (src / "sub").mkdir(exist_ok=True)
                (src / nested).write_text("gitdir: ../elsewhere\n")
                with self.assertRaisesRegex(harness.WorkerError, "nested git metadata: " + nested.replace(".", "\\.")):
                    harness.import_worktree(src, dst)
                (src / nested).unlink()
                self.assertFalse((dst / "a.txt").exists())
        (src / ".git").rmdir()
        (src / ".git").write_text("gitdir: /elsewhere\n")
        with self.assertRaisesRegex(harness.WorkerError, "git metadata replaced: .git"):
            harness.import_worktree(src, dst)

    def test_import_worktree_copies_content_without_reading_git(self):
        src, dst = Path(self.tmp.name) / "a", Path(self.tmp.name) / "b"
        (src / ".git").mkdir(parents=True), (dst / ".git").mkdir(parents=True)
        (src / ".git/config").write_text("[filter \"x\"]\n clean = touch " + str(self.mark) + "\n")
        (src / "d").mkdir()
        (src / "d/f.sh").write_text("x")
        (src / "d/f.sh").chmod(0o755)
        (dst / "stale.txt").write_text("old")
        (dst / ".git/keep").write_text("k")
        harness.import_worktree(src, dst)
        self.assertEqual((dst / "d/f.sh").read_text(), "x")
        self.assertTrue((dst / "d/f.sh").stat().st_mode & 0o111)
        self.assertFalse((dst / "stale.txt").exists())
        self.assertTrue((dst / ".git/keep").exists())
        self.assertFalse((dst / ".git/config").exists())
        self.assertFalse(self.mark.exists())

    def test_import_worktree_never_writes_through_symlinks(self):
        root = Path(self.tmp.name)
        src, dst, outside = root / "a", root / "b", root / "outside"
        for path in (src, dst, outside):
            path.mkdir()
        (dst / "a").symlink_to(outside)          # candidate head: directory symlink
        (src / "a").mkdir()                       # writer replaces it with a real directory
        (src / "a/payload").write_text("evil")
        (src / "link").symlink_to(outside)        # writer adds a directory symlink
        harness.import_worktree(src, dst)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((dst / "a").is_symlink())
        self.assertEqual((dst / "a/payload").read_text(), "evil")
        self.assertTrue((dst / "link").is_symlink())
        self.assertEqual(os.readlink(dst / "link"), str(outside))


if __name__ == "__main__":
    unittest.main()
