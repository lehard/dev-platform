from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'template/scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('local_workspace_under_test', SCRIPTS / 'local_workspace.py')
local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local)


@unittest.skipUnless(os.name == 'posix', 'POSIX permissions required')
class LocalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir()
        self.root = self.workspace / 'project'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.git('remote', 'add', 'origin', 'https://example.invalid/approved.git')
        (self.root / 'src').mkdir()
        (self.root / 'src/main.py').write_text('source\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.runtime = self.base / 'runtime'
        self.registry = self.base / 'registry.json'
        self.data = {'version': 1, 'runtime_dir': str(self.runtime), 'workspace_roots': [str(self.workspace)],
                     'projects': [{'origin': 'https://example.invalid/approved.git',
                                   'group': os.getegid(), 'source_roots': ['src']}]}
        self.registry.write_text(json.dumps(self.data))
        self.policy = {'version': 1, 'checkout': str(self.root), **self.data['projects'][0]}
        self.root.chmod(self.root.stat().st_mode | stat.S_ISGID)
        self.retains_setgid = bool(self.root.stat().st_mode & stat.S_ISGID)
        self.bits = local.expected_bits
        # The sandbox's Mac temporary volume strips setgid even on owner chmod.
        # Keep real rw repairs; isolate directory setgid support for composition tests.
        if not self.retains_setgid:
            patch = mock.patch.object(local, 'expected_bits', side_effect=lambda info: self.bits(info) & ~stat.S_ISGID)
            patch.start()
            self.addCleanup(patch.stop)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=True).stdout.strip()

    def attach(self):
        findings = local.sync(self.registry)
        self.assertEqual(findings, [])
        return Path(self.git('config', '--get', local.POLICY_KEY))

    def cli(self, *args, cwd=None, input=None):
        return subprocess.run([sys.executable, str(SCRIPTS / 'local_workspace.py'), *args],
                              cwd=cwd or self.root, text=True, capture_output=True, input=input)

    def test_restrictive_and_atomic_writes_owner_repair(self):
        source = self.root / 'src/main.py'
        source.chmod(0o600)
        self.assertTrue(any(str(source) in line for line in local.audit(self.root, self.policy)))
        self.assertEqual(local.audit(self.root, self.policy, repair=True), [])
        replacement = self.root / 'src/new'
        replacement.write_text('atomic\n')
        replacement.chmod(0o600)
        replacement.replace(source)
        self.assertTrue(local.audit(self.root, self.policy))
        self.assertEqual(local.audit(self.root, self.policy, repair=True), [])
        self.assertEqual(source.stat().st_mode & 0o060, 0o060)
        self.assertEqual(source.read_text(), 'atomic\n')
        bits = 0o2070 if self.retains_setgid else 0o070
        self.assertEqual((self.root / 'src').stat().st_mode & bits, bits)

    def test_tracked_source_outside_allowlist_remains_untouched(self):
        source = self.root / 'README.md'
        source.write_text('tracked')
        self.git('add', 'README.md')
        source.chmod(0o600)
        outside = self.root / 'private'
        outside.mkdir()
        untracked = outside / 'other'
        untracked.write_text('untracked')
        untracked.chmod(0o600)
        local.audit(self.root, self.policy, repair=True)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(untracked.stat().st_mode), 0o600)

    def test_excluded_secrets_caches_symlinks_and_hardlinks(self):
        for name in ('.env.local', 'private.key', 'credentials.json'):
            path = self.root / 'src' / name
            path.write_text('secret')
            path.chmod(0o600)
            self.git('add', str(path))
        cache = self.root / 'src/node_modules'
        cache.mkdir()
        (cache / 'dependency').write_text('cache')
        (cache / 'dependency').chmod(0o600)
        outside = self.base / 'outside'
        outside.write_text('outside')
        outside.chmod(0o600)
        (self.root / 'src/link').symlink_to(outside)
        os.link(outside, self.root / 'src/hardlink')
        findings = local.audit(self.root, self.policy, repair=True)
        self.assertTrue(any('hardlinked' in line for line in findings))
        for path in [outside, cache / 'dependency', self.root / 'src/.env.local', self.root / 'src/private.key',
                     self.root / 'src/credentials.json']:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_foreign_owner_reports_without_chmod(self):
        source = self.root / 'src/main.py'
        source.chmod(0o600)
        # Actual second-user sessions are unavailable; simulate caller ownership only.
        with mock.patch.object(local.os, 'geteuid', return_value=os.geteuid() + 100000), \
             mock.patch.object(local.os, 'fchmod') as chmod:
            findings = local.audit(self.root, self.policy, repair=True)
        chmod.assert_not_called()
        self.assertTrue(any(str(source) in line and 'owner uid=' in line for line in findings))
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o600)

    def test_foreign_worktree_refuses_launch_and_repair(self):
        task = self.base / 'task'
        self.git('worktree', 'add', '-qb', 'task', str(task))
        with mock.patch.object(local.os, 'geteuid', return_value=os.geteuid() + 100000):
            with self.assertRaisesRegex(local.PolicyError, 'foreign active worktree'):
                local.audit(task, self.policy, repair=True)
        self.assertFalse((task / 'ran').exists())

    def test_owner_worktree_source_and_admin_repair(self):
        task = self.base / 'task'
        self.git('worktree', 'add', '-qb', 'task', str(task))
        source = task / 'src/main.py'
        source.chmod(0o600)
        admin = Path(local.git(task, 'rev-parse', '--absolute-git-dir'))
        (admin / 'index').chmod(0o600)
        self.assertEqual(local.audit(task, self.policy, repair=True), [])
        self.assertEqual(source.stat().st_mode & 0o060, 0o060)
        self.assertEqual((admin / 'index').stat().st_mode & 0o060, 0o060)

    def test_hook_preserves_stdin_args_failure_and_doctor_refresh(self):
        hooks = self.root / 'operator-hooks'
        hooks.mkdir()
        self.git('config', 'core.hooksPath', 'operator-hooks')
        hook = hooks / 'pre-push'
        receipt = self.base / 'stdin'
        hook.write_text(f'#!/bin/sh\ncat > {receipt}\nprintf "%s\\n" "$@" >> {receipt}\nexit 17\n')
        hook.chmod(0o770)
        self.attach()
        dispatcher = Path(self.git('config', 'core.hooksPath')) / 'pre-push'
        result = subprocess.run([str(dispatcher), 'origin', '--odd-arg'], cwd=self.root, input='input\n',
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(receipt.read_text(), 'input\norigin\n--odd-arg\n')
        hook.write_text('#!/bin/sh\nexit 23\n')
        result = subprocess.run([str(dispatcher)], cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 23)
        local.detach(self.root)
        self.assertEqual(self.git('config', 'core.hooksPath'), 'operator-hooks')
        self.assertEqual(hook.read_text(), '#!/bin/sh\nexit 23\n')
        self.assertFalse(dispatcher.exists())

    def test_default_doctor_hook_refresh(self):
        hook = self.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 19\n')
        hook.chmod(0o770)
        self.attach()
        hook.write_text('#!/bin/sh\nexit 29\n')
        result = subprocess.run(['git', '-C', str(self.root), 'commit', '--allow-empty', '-m', 'rejected'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        dispatcher = Path(self.git('config', 'core.hooksPath')) / 'pre-commit'
        self.assertEqual(subprocess.run([str(dispatcher)], cwd=self.root).returncode, 29)

    def test_hook_invoked_in_git_directory_preserves_failure(self):
        hook = self.root / '.git/hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 41\n')
        hook.chmod(0o770)
        self.attach()
        dispatcher = Path(self.git('config', 'core.hooksPath')) / 'pre-receive'
        self.assertEqual(subprocess.run([str(dispatcher)], cwd=self.root / '.git').returncode, 41)

    def test_relative_operator_hook_uses_current_worktree(self):
        hooks = self.root / 'operator-hooks'
        hooks.mkdir()
        self.git('config', 'core.hooksPath', 'operator-hooks')
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\nexit 19\n')
        hook.chmod(0o770)
        self.git('add', 'operator-hooks')
        # Disable the hook only while creating the fixture commit.
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'hook fixture')
        task = self.workspace / 'task'
        self.git('worktree', 'add', '-qb', 'task', str(task))
        self.attach()
        (task / 'operator-hooks/pre-commit').write_text('#!/bin/sh\nexit 31\n')
        dispatcher = Path(self.git('config', 'core.hooksPath')) / 'pre-commit'
        self.assertEqual(subprocess.run([str(dispatcher)], cwd=task).returncode, 31)

    def test_operator_and_doctor_hooks_receive_same_input(self):
        hooks = self.root / 'operator-hooks'
        hooks.mkdir()
        self.git('config', 'core.hooksPath', 'operator-hooks')
        receipt = self.base / 'operator-input'
        hook = hooks / 'pre-commit'
        hook.write_text(f'#!/bin/sh\ncat > {receipt}\nprintf "%s\\n" "$@" >> {receipt}\n')
        hook.chmod(0o770)
        doctor_receipt = self.base / 'doctor-input'
        doctor = self.root / '.git/hooks/pre-commit'
        doctor.write_text(f'#!/bin/sh\n# Managed by dev-platform\ncat > {doctor_receipt}\nprintf "%s\\n" "$@" >> {doctor_receipt}\nexit 37\n')
        doctor.chmod(0o770)
        self.attach()
        dispatcher = Path(self.git('config', 'core.hooksPath')) / 'pre-commit'
        result = subprocess.run([str(dispatcher), 'argument'], cwd=self.root, input='hook input\n', text=True, capture_output=True)
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(receipt.read_text(), 'hook input\nargument\n')
        self.assertEqual(doctor_receipt.read_text(), receipt.read_text())

    def test_sync_repairs_current_user_task_under_reviewed_workspace(self):
        task = self.workspace / 'task'
        self.git('worktree', 'add', '-qb', 'task', str(task))
        self.attach()
        (task / 'src/main.py').chmod(0o600)
        admin = Path(local.git(task, 'rev-parse', '--absolute-git-dir'))
        (admin / 'index').chmod(0o600)
        self.assertEqual(local.sync(self.registry), [])
        self.assertEqual((task / 'src/main.py').stat().st_mode & 0o060, 0o060)
        self.assertEqual((admin / 'index').stat().st_mode & 0o060, 0o060)

    def test_sync_discovery_update_and_idempotence(self):
        other = self.workspace / 'unrelated'
        other.mkdir()
        subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(other), 'remote', 'add', 'origin', 'https://example.invalid/other.git'], check=True)
        policy = self.attach()
        runtime = self.runtime / 'local_workspace.py'
        timestamps = [path.stat().st_mtime_ns for path in (runtime, policy)]
        self.assertEqual(local.sync(self.registry), [])
        self.assertEqual(timestamps, [path.stat().st_mtime_ns for path in (runtime, policy)])
        runtime.write_text('stale runtime')
        self.assertEqual(local.sync(self.registry), [])
        self.assertEqual(runtime.read_bytes(), (SCRIPTS / 'local_workspace.py').read_bytes())
        self.assertNotIn('hooksPath', (other / '.git/config').read_text())
        self.assertNotIn('localWorkspacePolicy', (other / '.git/config').read_text())

    def test_installed_runtime_updates_from_clean_reviewed_source(self):
        source = self.workspace / 'platform'
        source.mkdir()
        subprocess.run(['git', '-C', str(source), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(source), 'config', 'user.email', 'test@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(source), 'config', 'user.name', 'Test'], check=True)
        subprocess.run(['git', '-C', str(source), 'remote', 'add', 'origin', 'https://example.invalid/platform.git'], check=True)
        runtime = source / 'runtime.py'
        runtime.write_bytes((SCRIPTS / 'local_workspace.py').read_bytes())
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(source), 'commit', '-qm', 'reviewed runtime'], check=True)
        branch = subprocess.run(['git', '-C', str(source), 'symbolic-ref', '--short', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
        self.data['runtime_source'] = {'checkout': str(source), 'origin': 'https://example.invalid/platform.git', 'branch': branch, 'path': 'runtime.py'}
        self.registry.write_text(json.dumps(self.data))
        self.attach()
        runtime.write_bytes(runtime.read_bytes() + b'\n# reviewed next version\n')
        with self.assertRaisesRegex(local.PolicyError, 'uncommitted'):
            local.sync(self.registry)
        subprocess.run(['git', '-C', str(source), 'commit', '-am', 'reviewed update', '-q'], check=True)
        installed = self.runtime / 'local_workspace.py'
        result = subprocess.run([sys.executable, str(installed), 'sync', '--registry', str(self.registry)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed.read_bytes(), runtime.read_bytes())

    def test_recovery_clone_is_excluded_by_checkout_name(self):
        clone = self.workspace / 'recovery'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(clone)], check=True)
        subprocess.run(['git', '-C', str(clone), 'remote', 'set-url', 'origin', self.policy['origin']], check=True)
        self.data['projects'][0]['checkout_names'] = ['project']
        self.registry.write_text(json.dumps(self.data))
        self.attach()
        self.assertIsNone(local.policy_for(clone))

    def test_generated_shared_state_can_be_updated_by_group_peer(self):
        self.attach()
        generated = self.runtime / 'runtime.json'
        with mock.patch.object(local.os, 'geteuid', return_value=os.geteuid() + 100000):
            local.write(generated, b'peer update\n')
        self.assertEqual(generated.read_bytes(), b'peer update\n')
        self.assertEqual(stat.S_IMODE(generated.stat().st_mode), 0o660)

    def test_modified_dispatcher_refuses_reattachment(self):
        self.attach()
        target = Path(self.git('config', 'core.hooksPath')) / 'pre-commit'
        target.write_text('operator change')
        self.assertTrue(any('generated hook changed' in item for item in local.sync(self.registry)))
        self.assertEqual(target.read_text(), 'operator change')

    def test_explicit_public_skills_without_private_agent_state(self):
        skills = self.root / '.agents/skills'
        skills.mkdir(parents=True)
        public = skills / 'SKILL.md'
        public.write_text('public instructions')
        public.chmod(0o600)
        private = self.root / '.agents/local.json'
        private.write_text('private')
        private.chmod(0o600)
        policy = dict(self.policy, source_roots=['src', '.agents/skills'])
        self.assertEqual(local.audit(self.root, policy, repair=True), [])
        self.assertEqual(public.stat().st_mode & 0o060, 0o060)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)

    def test_identity_group_and_broad_root_refused(self):
        bad = dict(self.policy, origin='https://example.invalid/wrong.git')
        with self.assertRaisesRegex(local.PolicyError, 'identity mismatch'):
            local.audit(self.root, bad, repair=True)
        with self.assertRaisesRegex(local.PolicyError, 'relative source root'):
            local.audit(self.root, dict(self.policy, source_roots=['../outside']))
        with mock.patch.object(local.os, 'getgroups', return_value=[]), \
             mock.patch.object(local.os, 'getegid', return_value=-1):
            with self.assertRaisesRegex(local.PolicyError, 'not a member'):
                local.audit(self.root, self.policy)
        with self.assertRaisesRegex(local.PolicyError, 'broad path'):
            local.absolute('/')

    def test_launcher_repairs_after_failed_atomic_writer_and_sets_umask(self):
        self.attach()
        script = "import os,pathlib; assert os.umask(2)==2; p=pathlib.Path('src/tmp'); p.write_text('new'); p.chmod(0o600); p.replace('src/main.py'); raise SystemExit(7)"
        with mock.patch.object(local.sys, 'argv', ['local_workspace.py', 'run', '--root', str(self.root), '--', sys.executable, '-c', script]):
            self.assertEqual(local.main(), 7)
        source = self.root / 'src/main.py'
        self.assertEqual(source.read_text(), 'new')
        self.assertEqual(source.stat().st_mode & 0o060, 0o060)

    def test_lifecycle_optin_readonly_admission(self):
        import shared_workspace
        local.audit(self.root, self.policy, repair=True)
        shared_workspace._admit_local_source(self.root)  # No opt-in.
        self.attach()
        source = self.root / 'src/main.py'
        source.chmod(0o600)
        import local_workspace
        with mock.patch.object(local_workspace, 'expected_bits', local.expected_bits):
            with self.assertRaisesRegex(shared_workspace.SharedWorkspaceError, 'local source admission blocked'):
                shared_workspace._admit_local_source(self.root)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o600)

    def test_changed_generated_hook_refuses_removal(self):
        self.attach()
        hooks = Path(self.git('config', 'core.hooksPath'))
        (hooks / 'pre-commit').write_text('foreign contents')
        with self.assertRaisesRegex(local.PolicyError, 'generated hook changed'):
            local.detach(self.root)
        self.assertEqual(self.git('config', 'core.hooksPath'), str(hooks))

    def test_setgid_requirement_and_unsupported_volume_diagnostic(self):
        self.assertEqual(self.bits(self.root.stat()), 0o2070)
        with mock.patch.object(local, 'expected_bits', self.bits):
            findings = local.audit(self.root, self.policy, repair=True)
        if not self.retains_setgid:
            self.assertTrue(any(str(self.root) in item and 'g+rwxs' in item for item in findings))

    def test_launchagent_per_user_idempotent_and_remove(self):
        self.attach()
        home = self.base / 'home'
        home.mkdir()
        destination = home / 'Library/LaunchAgents/dev.platform.local-workspace.plist'
        with mock.patch.object(local.sys, 'platform', 'darwin'), \
             mock.patch.object(local.Path, 'home', return_value=home), \
             mock.patch.object(local.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            local.launchagent(self.registry, destination)
            payload = local.plistlib.loads(destination.read_bytes())
            self.assertEqual(payload['Umask'], 2)
            self.assertEqual(payload['StartInterval'], 300)
            self.assertIn(str(self.registry), payload['ProgramArguments'])
            timestamp = destination.stat().st_mtime_ns
            local.launchagent(self.registry, destination)
            self.assertEqual(destination.stat().st_mtime_ns, timestamp)
            self.assertTrue(any(call.args[0][1] == 'bootstrap' for call in run.call_args_list))
            local.launchagent(self.registry, destination, remove=True)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
