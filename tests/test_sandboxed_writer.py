from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402


def setUpModule() -> None:
    sys.path.insert(0, str(ROOT / "template" / "scripts"))

workers = load_platform_module("lifecycle_workers", ROOT / "template/scripts/lifecycle_workers.py")
sw = load_platform_module("sandboxed_writer", ROOT / "template/scripts/sandboxed_writer.py")
SECRET = "sk-ant-oat01-SECRETVALUE"


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


class Base(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.tmp = Path(os.path.realpath(self._dir.name))

    def config(self, mode=0o600, content=SECRET + "\n"):
        path = self.tmp / "token"
        path.write_text(content)
        path.chmod(mode)
        return {"independent_review": {"login": {"claude": {"token_file": str(path)}}}}


class ProfileTests(Base):
    def profile(self, **kw):
        args = dict(checkout=self.tmp / "co", home=self.tmp / "home", tmp=self.tmp / "tmp",
                    protected=[str(self.tmp / "integration")], platform_root=self.tmp / "platform")
        args.update(kw)
        return sw.build_profile(**args)

    def test_content(self):
        p = self.profile()
        self.assertEqual(p["network"], {"allowedDomains": ["api.anthropic.com", "claude.ai", "platform.claude.com"],
                                        "deniedDomains": []})
        fs = p["filesystem"]
        self.assertEqual(fs["allowWrite"], [str(self.tmp / n) for n in ("co", "home", "tmp")])
        self.assertIn(str(self.tmp / "integration"), fs["denyWrite"])
        self.assertIn(str(self.tmp / "platform"), fs["denyWrite"])
        for entry in ("~/.claude", "~/.claude.json", "~/.config", "~/.ssh"):
            self.assertIn(entry, fs["denyWrite"])
        for entry in ("~/.ssh", "~/.config/gh", "~/.gitconfig", "~/.git-credentials", "~/.netrc", "~/.aws", "~/.gnupg",
                      "~/Library/Keychains", "~/.claude", "~/.claude.json", "~/.config/dev-platform",
                      "~/Library/Application Support", "~/.npmrc", "~/.docker"):
            self.assertIn(entry, fs["denyRead"])
        self.assertIn(str(self.tmp / "integration"), fs["denyRead"])

    def test_no_apple_events_or_weaker_isolation(self):
        text = str(self.profile())
        self.assertNotIn("allowAppleEvents", text)
        self.assertNotIn("enableWeakerNetworkIsolation", text)

    def test_refuses_writable_inside_protected(self):
        with self.assertRaises(sw.SandboxedWriterError):
            self.profile(checkout=self.tmp / "integration" / "sub")
        with self.assertRaises(sw.SandboxedWriterError):
            self.profile(home=self.tmp / "integration")
        with self.assertRaises(sw.SandboxedWriterError):
            self.profile(tmp=self.tmp / "platform")
        with self.assertRaises(sw.SandboxedWriterError):
            self.profile(extra_deny_write=[str(self.tmp / "home")])

    def test_profile_file_outside_writable_roots(self):
        p = self.profile()
        with self.assertRaises(sw.SandboxedWriterError):
            sw.write_profile(p, self.tmp / "co" / "s.json")
        path = sw.write_profile(p, self.tmp / "work" / "s.json")
        self.assertTrue(path.is_file())


class ProtectedPathTests(Base):
    def test_includes_worktrees_and_common_dir(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "x")
        wt = self.tmp / "wt"
        git(repo, "worktree", "add", "-q", "-b", "b", str(wt))
        paths = sw.protected_paths(repo)
        self.assertIn(str(repo), paths)
        self.assertIn(str(repo / ".git"), paths)
        self.assertIn(str(wt), paths)

    def test_not_a_repo_raises(self):
        with self.assertRaises(sw.SandboxedWriterError):
            sw.protected_paths(self.tmp)


class TokenTests(Base):
    def test_reads_token(self):
        self.assertEqual(sw.read_claude_token(self.config()), SECRET)

    def test_refusals_never_leak_token(self):
        cases = [{}, {"independent_review": {}}, {"independent_review": {"login": {"claude": {}}}},
                 self.config(mode=0o644)]
        for cfg in cases:
            with self.assertRaises(sw.SandboxedWriterError) as ctx:
                sw.read_claude_token(cfg)
            self.assertNotIn(SECRET, str(ctx.exception))
        self.assertIn("0600", str(sw.SandboxedWriterError("0600")))

    def test_missing_key_names_setting(self):
        with self.assertRaisesRegex(sw.SandboxedWriterError, r"independent_review.login.claude\] token_file"):
            sw.read_claude_token({})

    def test_mode_error_names_file_and_mode(self):
        cfg = self.config(mode=0o644)
        with self.assertRaisesRegex(sw.SandboxedWriterError, "token.*0600"):
            sw.read_claude_token(cfg)

    def test_missing_file_and_empty(self):
        cfg = self.config()
        Path(cfg["independent_review"]["login"]["claude"]["token_file"]).unlink()
        with self.assertRaises(sw.SandboxedWriterError):
            sw.read_claude_token(cfg)
        with self.assertRaisesRegex(sw.SandboxedWriterError, "empty"):
            sw.read_claude_token(self.config(content="  \n"))


class CommandTests(Base):
    def test_shape_and_multiword_task(self):
        argv = ["claude", "-p", "do the multi word task 'quoted'"]
        cmd = sw.sandboxed_command(argv, launcher=["srt"], profile_path=Path("/p.json"), writer_tmp=Path("/w/tmp"))
        self.assertEqual(cmd[:5], ["srt", "--settings", "/p.json", "env", "TMPDIR=/w/tmp"])
        self.assertIn("CLAUDE_CODE_TMPDIR=/w/tmp", cmd)
        self.assertEqual(cmd[-3:-1], ["bash", "-c"])
        self.assertEqual(shlex.split(cmd[-1]), argv)
        plain = sw.sandboxed_command(argv, launcher=["srt"], profile_path=Path("/p"), writer_tmp=Path("/w"), claude=False)
        self.assertNotIn("CLAUDE_CODE_TMPDIR=/w", plain)

    def test_launcher_pinned_and_requires_npx(self):
        with mock.patch.object(sw.shutil, "which", return_value="/x/npx"):
            self.assertEqual(sw.srt_launcher(), ["npx", "--yes", "@anthropic-ai/sandbox-runtime@0.0.79"])
        with mock.patch.object(sw.shutil, "which", return_value=None):
            with self.assertRaisesRegex(sw.SandboxedWriterError, "npx"):
                sw.srt_launcher()
            with self.assertRaisesRegex(sw.SandboxedWriterError, "claude"):
                sw.require_writer_cli()

    def test_non_darwin_refused(self):
        with mock.patch.object(sw.sys, "platform", "linux"):
            with self.assertRaisesRegex(sw.SandboxedWriterError, "only on macOS"):
                sw.require_macos()
        with mock.patch.object(sw.sys, "platform", "darwin"):
            sw.require_macos()


class LaunchTests(Base):
    def test_token_only_in_writer_env(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "x")
        calls = []

        def runner(command, **kw):
            calls.append((command, kw))
            return subprocess.CompletedProcess(command, 0, "", "")

        co, home, wtmp, work = (self.tmp / n for n in ("co", "home", "wtmp", "work"))
        for d in (co, home, wtmp):
            d.mkdir()
        cfg = self.config()
        with mock.patch.object(sw.sys, "platform", "darwin"), \
                mock.patch.object(sw.shutil, "which", return_value="/x/bin"), \
                mock.patch.object(sw, "srt_tmp", return_value=Path("/private/tmp/dp-srt-test")), \
                mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "ambient-secret"}):
            sw.launch_sandboxed_writer(["claude", "-p", "a b"], co, integration_root=repo, platform_root=self.tmp / "plat",
                                       workdir=work, home=home, tmp=wtmp, config=cfg, runner=runner)
            self.assertEqual(os.environ["CLAUDE_CODE_OAUTH_TOKEN"], "ambient-secret")
        command, kw = calls[0]
        self.assertEqual(kw["env"]["CLAUDE_CODE_OAUTH_TOKEN"], SECRET)
        self.assertEqual(kw["env"]["TMPDIR"], "/private/tmp/dp-srt-test")
        self.assertIn(f"TMPDIR={wtmp}", command)
        self.assertNotIn(SECRET, " ".join(command))
        self.assertNotIn("ambient-secret", str(kw["env"]))
        self.assertTrue((work / "srt-settings.json").is_file())

    def test_harness_envs_drop_ambient_token(self):
        repo = self.tmp / "h"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "remote", "add", "origin", str(self.tmp))
        env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": SECRET}
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", workers.harness_push_env(repo, env))
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": SECRET}), \
                mock.patch.object(workers.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            workers.harness_git(repo, "status")
            self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", run.call_args.kwargs["env"])

    def test_run_llm_default_unchanged(self):
        seen = {}
        workers.run_llm(["x"], self.tmp, tmp=Path("/w"), env={"A": "1"},
                        runner=lambda c, **kw: seen.update(kw) or None)
        self.assertEqual(seen["env"]["TMPDIR"], "/w")


if __name__ == "__main__":
    unittest.main()
