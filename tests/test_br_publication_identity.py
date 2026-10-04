"""Synthetic publication boundary tests; no live repositories or GitHub writes."""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'template/scripts'))
import managed_work_identity as identity
import managed_task
import requirement_integration as ri
import project_publish as publish
import start_managed_task as start
import start_worktree
import execute_requirement


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, text=True, capture_output=True).stdout.strip()


def claims(source='acme/backlog#8', value='BR-7/T1'):
    return {
        source: {'body': f'Requirement: acme/backlog#7\nWork identity: {value}\n', 'labels': [{'name': 'type:internal-change'}]},
        'acme/backlog#7': {'body': f'Work identity: BR-7\n<!-- br-child:{source}:1 -->\n<!-- requirement-children:start -->\n- [ ] {source}\n<!-- requirement-children:end -->', 'labels': [{'name': 'type:requirement'}]},
    }


class IdentityPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def canonical(self, bodies, **kwargs):
        with mock.patch.object(managed_task, 'fetch_issue', side_effect=lambda root, repo, num: bodies[f'{repo}#{num}']):
            return identity.canonical_child_identity(self.root, 'acme/backlog#8', **kwargs)

    def test_canonical_claim_and_provenance_must_agree(self):
        self.assertEqual(self.canonical(claims(), provenance={'work_identity': 'BR-7/T1'}), 'BR-7/T1')
        with self.assertRaisesRegex(identity.IdentityError, 'provenance'):
            self.canonical(claims(), provenance={'work_identity': 'BR-7/T2'})
        with self.assertRaisesRegex(identity.IdentityError, 'canonical parent'):
            self.canonical(claims(), requirement='acme/backlog#9')
        bodies = claims(value='BR-9/T1')
        with self.assertRaises(identity.IdentityError):
            self.canonical(bodies)
        bodies = claims()
        bodies['acme/backlog#7']['body'] = 'Work identity: BR-7'
        with self.assertRaisesRegex(identity.IdentityError, 'reciprocal'):
            self.canonical(bodies)

    def test_sibling_duplicate_identity_fails_closed(self):
        bodies = claims()
        bodies['acme/backlog#7']['body'] = ('Work identity: BR-7\n<!-- requirement-children:start -->\n'
                                           '- [ ] acme/backlog#8\n- [ ] acme/backlog#9\n<!-- requirement-children:end -->')
        bodies['acme/backlog#9'] = {'body': 'Requirement: acme/backlog#7\nWork identity: BR-7/T1\n',
                                    'labels': [{'name': 'type:internal-change'}]}
        with self.assertRaisesRegex(identity.IdentityError, 'duplicate child ordinal'):
            self.canonical(bodies)

    def test_unlinked_and_legacy_provenance(self):
        with mock.patch.object(managed_task, 'fetch_issue', return_value={'body': '', 'labels': []}):
            self.assertIsNone(identity.canonical_child_identity(self.root, 'acme/backlog#8'))
            with self.assertRaises(identity.IdentityError):
                identity.canonical_child_identity(self.root, 'acme/backlog#8', provenance={'work_identity': 'BR-7/T1'})
        self.assertEqual(self.canonical(claims(), provenance={}), 'BR-7/T1')

    def test_branch_and_title_body_are_safe_and_idempotent(self):
        self.assertEqual(identity.task_branch('change', 'BR-7/T2'), 'agent/br-7-t2-change')
        self.assertEqual(identity.task_branch('change'), 'agent/change')
        for value in ('BR-7/T2\nacme/backlog#8', 'BR-0/T1', 'BR-7', 'secret'):
            with self.assertRaises(identity.IdentityError):
                identity.task_branch('change', value)
        title, body = identity.presentation('[BR-9/T4] User title', 'User prose\n', 'BR-7/T2')
        self.assertEqual(title, '[BR-7/T2] User title')
        self.assertTrue(body.startswith('User prose\n'))
        self.assertEqual(identity.presentation(title, body, 'BR-7/T2'), (title, body))
        shared = identity.presentation('Shared', 'User prose', 'BR-7', ['BR-7/T1'])
        grown = identity.presentation(*shared, 'BR-7', ['BR-7/T1', 'BR-7/T2'])
        self.assertEqual(grown[0], '[BR-7] Shared')
        self.assertIn('Included children: BR-7/T1, BR-7/T2', grown[1])
        self.assertEqual(grown[1].count(identity.BLOCK_START), 1)
        for children in (['BR-8/T1'], ['BR-7/T1', 'BR-7/T1']):
            with self.assertRaises(identity.IdentityError):
                identity.presentation('', '', 'BR-7', children)
        with self.assertRaises(identity.IdentityError):
            identity.presentation('', identity.BLOCK_START, 'BR-7/T1')

    def test_exact_head_retry_repairs_existing_user_content_once(self):
        head = 'a' * 40
        old = {'title': '[BR-9/T2] User title', 'body': 'User description', 'headRefOid': head}
        pr = {'number': 4, 'url': 'https://example.invalid/pr/4'}
        lookup = SimpleNamespace(available=True, exact_open=pr, exact_merged=None)
        current = dict(old)
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            if command[2] == 'view':
                return SimpleNamespace(stdout=json.dumps(current))
            if command[2] == 'edit':
                current['title'] = command[command.index('--title') + 1]
                current['body'] = command[command.index('--body') + 1]
                return SimpleNamespace(stdout='')
            self.fail('unexpected creation or mutation')
        with mock.patch.object(publish.subprocess, 'run', side_effect=run):
            for _ in range(2):
                result = publish.ensure_pr(self.root, {}, 'agent/legacy', 'main', 'Ignored supplied title', 'Ignored supplied body', head,
                                           lookup=lookup, identity='BR-7/T1')
        self.assertEqual(result.number, 4)
        self.assertEqual(current['title'], '[BR-7/T1] User title')
        self.assertTrue(current['body'].startswith('User description'))
        self.assertEqual(sum(command[2] == 'edit' for command in commands), 1)

    def test_creation_and_create_race_use_safe_identity_and_same_exact_pr(self):
        head = 'a' * 40
        empty = SimpleNamespace(available=True, exact_open=None, exact_merged=None)
        found = SimpleNamespace(available=True, exact_open={'number': 4, 'url': 'https://example.invalid/pr/4'}, exact_merged=None)
        for returncode in (0, 1):
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                if command[2] == 'create':
                    return SimpleNamespace(returncode=returncode, stdout='https://example.invalid/pr/4', stderr='race')
                if command[2] == 'view':
                    return SimpleNamespace(stdout=json.dumps({'headRefOid': head, 'title': 'Race winner title', 'body': 'User race winner description'}))
                return SimpleNamespace(stdout='')
            with mock.patch.object(publish.subprocess, 'run', side_effect=run), mock.patch.object(publish, 'find_exact_head_pr', return_value=found):
                result = publish.ensure_pr(self.root, {}, 'agent/br-7-t1-change', 'main', 'New title', 'New body', head,
                                          lookup=empty, identity='BR-7/T1', draft=True)
            self.assertEqual(result.number, 4)
            self.assertEqual(sum(command[2] == 'create' for command in commands), 1)
            self.assertIn('[BR-7/T1] New title', commands[0])
            self.assertIn('--draft', commands[0])
            self.assertIn('[BR-7/T1] Race winner title', commands[-1])
            self.assertIn('User race winner description', commands[-1][-1])

    def test_shared_growth_repairs_same_pr_with_all_children(self):
        head = 'a' * 40
        current = {'title': 'User shared title', 'body': 'User shared body', 'headRefOid': head}
        pr = {'number': 4, 'url': 'https://example.invalid/pr/4'}
        lookup = SimpleNamespace(available=True, exact_open=pr, exact_merged=None)
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            if command[2] == 'view':
                return SimpleNamespace(stdout=json.dumps(current))
            self.assertEqual(command[2], 'edit')
            self.assertEqual(command[3], '4')
            current['title'] = command[command.index('--title') + 1]
            current['body'] = command[command.index('--body') + 1]
            return SimpleNamespace(stdout='')
        with mock.patch.object(publish.subprocess, 'run', side_effect=run):
            for included in (['BR-7/T1'], ['BR-7/T1', 'BR-7/T2'], ['BR-7/T1', 'BR-7/T2']):
                publish.ensure_pr(self.root, {}, 'agent/shared', 'main', None, None, head, lookup=lookup,
                                  identity='BR-7', children=included, draft=True)
        self.assertEqual(current['title'], '[BR-7] User shared title')
        self.assertEqual(sum(command[2] == 'edit' for command in commands), 2)
        self.assertTrue(current['body'].startswith('User shared body'))
        self.assertIn('Included children: BR-7/T1, BR-7/T2', current['body'])

    def test_publication_rejects_provenance_mismatch_before_push(self):
        delivery = SimpleNamespace(source_issue='acme/backlog#8', path=self.root)
        bodies = claims()
        with mock.patch.object(publish, 'require_delivery_provenance', return_value=delivery), \
             mock.patch.object(publish, 'require_independent_publication_exception'), \
             mock.patch.object(managed_task, 'read_provenance', return_value={'work_identity': 'BR-7/T2'}), \
             mock.patch.object(managed_task, 'fetch_issue', side_effect=lambda root, repo, num: bodies[f'{repo}#{num}']), \
             mock.patch.object(publish, 'push_feature_branch') as push:
            with self.assertRaisesRegex(SystemExit, 'committed provenance'):
                publish.publish_pr(self.root, 'origin', 'main', None, None, 'manual')
        push.assert_not_called()

    def test_shared_canonical_claims_are_rechecked_after_long_validation(self):
        import _platform_common
        manifest = {'requirement': 'acme/backlog#7', 'children': [{}, {}]}
        head = 'a' * 40
        with mock.patch.object(_platform_common, 'main_root', return_value=self.root), \
             mock.patch.object(_platform_common, 'read_platform_config', return_value={'publish_mode': 'pr'}), \
             mock.patch.object(ri, '_validate_candidate_checkout', return_value=('agent/shared', head)), \
             mock.patch.object(ri, '_reconcile_exact_merged', return_value=None), \
             mock.patch.object(ri, 'compose_candidate', return_value={'head': head, 'resumed': True}), \
             mock.patch.object(ri, '_verify_parent_links'), \
             mock.patch.object(ri, '_run_full_checks') as checks, \
             mock.patch.object(ri, 'publication_identities', side_effect=[('BR-7', ['BR-7/T1', 'BR-7/T2']), ('BR-7', ['BR-7/T1', 'BR-7/T3'])]) as proof, \
             mock.patch.object(ri.subprocess, 'run') as publisher:
            with self.assertRaisesRegex(ri.RequirementIntegrationError, 'changed after validation'):
                ri.publish_candidate(self.root, manifest=manifest, receipt_paths=[])
        checks.assert_called_once_with(self.root)
        self.assertEqual(proof.call_count, 2)
        publisher.assert_not_called()

    def test_head_race_and_privacy_guard_block_edits(self):
        pr = publish.PrRef(4, 'https://example.invalid/pr/4')
        with mock.patch.object(publish.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps({'headRefOid': 'b' * 40}))) as run:
            with self.assertRaisesRegex(SystemExit, 'head changed'):
                publish._repair_pr_identity(self.root, {}, pr, 'a' * 40, 'BR-7/T1', None)
            self.assertEqual(run.call_count, 1)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/check_private_backlog_refs.py').write_text('')
        observed = SimpleNamespace(stdout=json.dumps({'headRefOid': 'a' * 40, 'title': 'User', 'body': 'acme/backlog#8'}))
        with mock.patch.object(publish.subprocess, 'run', side_effect=[observed, subprocess.CalledProcessError(1, 'guard')]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                publish._repair_pr_identity(self.root, {}, pr, 'a' * 40, 'BR-7/T1', None)
            self.assertEqual(run.call_count, 2)
            self.assertNotIn('edit', run.call_args.args[0])

    def test_registered_legacy_transaction_keeps_branch(self):
        package = SimpleNamespace(change='change', work_identity='BR-7/T1', source_issue='acme/backlog#8',
                                  target_repository='acme/project', revision='r')
        worktrees = self.root / 'worktrees'
        worktree = worktrees / 'change'
        worktree.mkdir(parents=True)
        with mock.patch.object(start, 'machine_path', return_value=worktrees), \
             mock.patch.object(start, '_registered_worktree_branches', return_value={worktree.resolve(): 'agent/change'}), \
             mock.patch.object(start, 'utc_now', return_value='now'), \
             mock.patch.object(start, 'canonical_provenance_candidates', return_value=[object()]), \
             mock.patch.object(start, 'resolve_canonical_provenance'):

            with start.managed_start_transaction(self.root, package) as (transaction, created):
                self.assertTrue(created)
                self.assertEqual(transaction['branch'], 'agent/change')
                self.assertEqual(transaction['worktree'], str(worktree))

    def test_transaction_recovery_keeps_legacy_ref_without_registered_worktree(self):
        package = SimpleNamespace(change='change', work_identity='BR-7/T1', source_issue='acme/backlog#8',
                                  target_repository='acme/project', revision='r')
        worktrees = self.root / 'worktrees'
        path = start._transaction_path(worktrees, 'change')
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'version': 1, 'state': 'creating', 'attempt_id': 'synthetic-attempt', 'source_issue': package.source_issue,
            'target_repository': package.target_repository, 'change': 'change', 'package_revision': 'r',
            'base_child_digest': None, 'branch': 'agent/change', 'worktree': str(worktrees / 'change')}))
        with mock.patch.object(start, 'machine_path', return_value=worktrees):
            with start.managed_start_transaction(self.root, package) as (transaction, created):
                self.assertFalse(created)
                self.assertEqual(transaction['branch'], 'agent/change')

    def test_real_worktree_creation_decouples_br_branch_from_change_path(self):
        git(self.root, 'init', '-b', 'main')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'user.name', 'Test')
        scripts = self.root / 'scripts'
        scripts.mkdir()
        (scripts / 'agent_board.py').write_text('import sys\nif sys.argv[1] == "start": print("synthetic-board")\n')
        (self.root / '.gitignore').write_text('.claude/\n')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'synthetic baseline')
        branch = identity.task_branch('change', 'BR-7/T1')
        with mock.patch.object(start_worktree, 'preflight'), \
             mock.patch.object(start_worktree, 'read_platform_config', return_value={'workflow_profile': 'multi-agent', 'main_branch': 'main'}), \
             mock.patch.object(start_worktree, 'machine_path', return_value=self.root / '.claude/worktrees'):
            created = start_worktree.create_worktree(self.root, 'change', 'Synthetic task', sync=False, branch_name=branch)
        self.assertEqual(created.worktree.name, 'change')
        self.assertEqual(created.branch, 'agent/br-7-t1-change')
        self.assertEqual(ri._registered_worktrees(self.root)[created.worktree], branch)
        self.assertEqual(git(created.worktree, 'branch', '--show-current'), branch)
        self.assertEqual(git(self.root, 'branch', '--show-current'), 'main')

    def test_import_identity_race_rolls_back_only_the_created_branch(self):
        package = SimpleNamespace(change='change', work_identity='BR-7/T1', source_issue='acme/backlog#8', revision='r')
        created = start.StartedTask(profile='multi-agent', branch='agent/br-7-t1-change', task_root=self.root / 'change')
        imported = SimpleNamespace(work_identity='BR-7/T2')
        with mock.patch.object(start, 'start_task', return_value=created), \
             mock.patch.object(start, 'import_task', return_value=(imported, 'a' * 40, False)), \
             mock.patch.object(start, 'cleanup_started_task') as cleanup, \
             mock.patch.object(start, 'admit_task') as admission:
            with self.assertRaisesRegex(start.ManagedTaskError, 'identity changed'):
                start._start_new_managed_task(self.root, package, package.source_issue, '', None)
        cleanup.assert_called_once_with(self.root, created)
        admission.assert_not_called()

    def test_foreign_registered_branch_cannot_be_adopted_for_recovery(self):
        package = SimpleNamespace(change='change', work_identity='BR-7/T1', source_issue='acme/backlog#8',
                                  target_repository='acme/project', revision='r')
        worktrees = self.root / 'worktrees'
        worktree = worktrees / 'change'
        worktree.mkdir(parents=True)
        with mock.patch.object(start, 'machine_path', return_value=worktrees), \
             mock.patch.object(start, '_registered_worktree_branches', return_value={worktree: 'agent/foreign'}), \
             mock.patch.object(start, 'canonical_provenance_candidates', return_value=[]):
            with self.assertRaisesRegex(start.ManagedTaskError, 'refusing takeover'):
                with start.managed_start_transaction(self.root, package):
                    self.fail('foreign worktree was adopted')
        self.assertTrue(worktree.is_dir())

    def test_legacy_project_start_signature_stops_new_linked_branch(self):
        package = SimpleNamespace(change='change', work_identity='BR-7/T1', source_issue='acme/backlog#8',
                                  target_repository='acme/project', revision='r')
        calls = []
        def owned_start(root, slug, task, scope, *, admission=True):
            calls.append(slug)
            raise RuntimeError('project-owned creation reached')
        with mock.patch.object(start, 'start_task', owned_start), mock.patch.object(start, 'machine_path', return_value=self.root / 'worktrees'):
            with self.assertRaisesRegex(start.ManagedTaskError, 'must accept branch_name'):
                with start.managed_start_transaction(self.root, package):
                    self.fail('incompatible helper admitted a new linked branch')
            with self.assertRaisesRegex(start.ManagedTaskError, 'must accept branch_name'):
                start._start_new_managed_task(self.root, package, package.source_issue, '', None)
            package.work_identity = None
            with start.managed_start_transaction(self.root, package) as (transaction, _):
                self.assertEqual(transaction['branch'], 'agent/change')
            with self.assertRaisesRegex(RuntimeError, 'project-owned creation reached'):
                start._start_new_managed_task(self.root, package, package.source_issue, '', None)
            package.work_identity = 'BR-7/T1'
            path = start._transaction_path(self.root / 'worktrees', 'change')
            path.write_text(json.dumps({'version': 1, 'state': 'creating', 'attempt_id': 'synthetic-attempt',
                'source_issue': package.source_issue, 'target_repository': package.target_repository,
                'change': package.change, 'package_revision': package.revision, 'base_child_digest': None,
                'branch': 'agent/change', 'worktree': str(self.root / 'worktrees/change')}))
            with start.managed_start_transaction(self.root, package) as (transaction, _):
                self.assertEqual(transaction['branch'], 'agent/change')
            with self.assertRaisesRegex(RuntimeError, 'project-owned creation reached'):
                start._start_new_managed_task(self.root, package, package.source_issue, '', None, branch_name='agent/change')
        self.assertEqual(calls, ['change', 'change'])

    def test_new_transaction_and_creation_share_branch_identity(self):
        package = SimpleNamespace(change='change', work_identity='BR-7/T1', source_issue='acme/backlog#8',
                                  target_repository='acme/project', revision='r')
        with mock.patch.object(start, 'machine_path', return_value=self.root / 'worktrees'):
            with start.managed_start_transaction(self.root, package) as (transaction, _):
                self.assertEqual(transaction['branch'], 'agent/br-7-t1-change')
        with mock.patch.object(start, 'start_task', side_effect=RuntimeError('stop at creation')) as create:
            with self.assertRaisesRegex(RuntimeError, 'stop at creation'):
                start._start_new_managed_task(self.root, package, package.source_issue, '', None)
        self.assertEqual(create.call_args.kwargs['branch_name'], 'agent/br-7-t1-change')

    def test_receipt_discovery_uses_registered_branch(self):
        (self.root / 'worktrees/change').mkdir(parents=True)
        wt = self.root / 'worktrees/change'
        with mock.patch.object(execute_requirement, 'machine_path', return_value=self.root / 'worktrees'), \
             mock.patch.object(ri, '_registered_worktrees', return_value={wt.resolve(): 'agent/br-7-t1-change'}), \
             mock.patch.object(execute_requirement, '_git', return_value='agent/br-7-t1-change'), \
             mock.patch.object(execute_requirement.managed_task, 'resolve_canonical_provenance', return_value=None) as canonical:
            self.assertIsNone(execute_requirement._ready_receipt(self.root, self.root, 'acme/backlog#7', 'acme/backlog#8', 'change'))
        canonical.assert_called_once_with(wt, source_issue='acme/backlog#8', change='change')

    def test_additive_manifest_preserves_opaque_lineage_and_rejects_mismatch(self):
        private = {'version': 1, 'requirement': 'acme/backlog#7', 'work_identity': 'BR-7', 'children': [
            {'source_issue': 'acme/backlog#8', 'change': 'one', 'work_identity': 'BR-7/T1'}]}
        private['digest'] = ri._digest(private)
        def handle(root, source, change, create=False):
            return 'pln_' + ('1' if source.endswith('#7') else '2') * 32
        with mock.patch('private_lineage.enabled', return_value=True), mock.patch('private_lineage.handle_for_issue', side_effect=handle):
            public = ri._public_manifest(self.root, private)
        self.assertNotIn('acme/backlog', json.dumps(public))
        self.assertEqual(public['children'][0]['work_identity'], 'BR-7/T1')
        legacy = {key: value for key, value in public.items() if key not in ('work_identity', 'digest')}
        legacy['children'] = [{key: value for key, value in public['children'][0].items() if key != 'work_identity'}]
        legacy['digest'] = ri._digest(legacy)
        self.assertTrue(ri._presentation_upgrade(legacy, public))
        bad = {**public, 'requirement': 'pln_' + '3' * 32}
        self.assertFalse(ri._presentation_upgrade(legacy, bad))
        private['work_identity'] = 'BR-8'
        with self.assertRaisesRegex(ri.RequirementIntegrationError, 'disagrees'):
            ri._public_manifest(self.root, private)

    @unittest.skipUnless(shutil.which('copier'), 'Copier unavailable')
    def test_current_template_render_preserves_project_owned_upgrade_surfaces(self):
        source = Path(__file__).resolve().parents[1]
        snapshot = self.root / 'synthetic-template'
        snapshot.mkdir()
        shutil.copy2(source / 'copier.yml', snapshot / 'copier.yml')
        shutil.copytree(source / 'template', snapshot / 'template', ignore=shutil.ignore_patterns('__pycache__'))
        owned = ('AGENTS.md', 'scripts/project_publish.py', 'scripts/start_task.py', 'docs/engineering/agent-workflow.md')
        sentinel = '# Synthetic project-owned sentinel\n'
        for harness in ('platform', 'project'):
            target = self.root / harness
            if harness == 'project':
                for relative in owned:
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(sentinel)
            command = ['copier', 'copy', '--trust', '--defaults', '--skip-tasks', '--overwrite', '--quiet',
                       '--data', 'project_name=Synthetic Identity', '--data', 'project_slug=synthetic-identity',
                       '--data', 'workflow_profile=multi-agent', '--data', f'harness_mode={harness}', str(snapshot), str(target)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('def presentation(', (target / 'scripts/managed_work_identity.py').read_text())
            self.assertIn('Readable managed publication identity', (target / 'docs/engineering/task-intake.md').read_text())
            result = subprocess.run([sys.executable, '-m', 'compileall', '-q', str(target / 'scripts')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            if harness == 'project':
                for relative in owned:
                    self.assertEqual((target / relative).read_text(), sentinel)

    def test_two_child_branch_manifest_growth_and_generation_path_ownership(self):
        import requirement_intake
        git(self.root, 'init', '-b', 'main')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'user.name', 'Test')
        (self.root / 'base').write_text('base')
        (self.root / '.gitignore').write_text('.managed-task-state.json\n.claude/\n')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'base')
        base = git(self.root, 'rev-parse', 'HEAD')
        receipts = []
        for ordinal, change in enumerate(('one', 'two'), 1):
            source = f'acme/backlog#{7 + ordinal}'
            branch = identity.task_branch(change, f'BR-7/T{ordinal}')
            git(self.root, 'switch', '-c', branch)
            (self.root / f'{change}.txt').write_text(change)
            archive = self.root / f'openspec/changes/archive/2026-10-04-{change}'
            archive.mkdir(parents=True)
            (archive / '.managed-task.json').write_text(json.dumps({'source_issue': source, 'change': change, 'work_identity': f'BR-7/T{ordinal}'}))
            (archive / 'verification.md').write_text('OpenSpec-Verify: PASS\nVerification-Method: synthetic fixture\n')
            (archive / 'tasks.md').write_text('- [x] Synthetic fixture\n')
            (archive / 'automated-checks.json').write_text(json.dumps({'outcome': 'success', 'executed_commands': [{'outcome': 'success'}]}))
            git(self.root, 'add', '.')
            git(self.root, 'commit', '-m', change)
            (self.root / '.managed-task-state.json').write_text(json.dumps({'source_issue': source, 'change': change}))
            with mock.patch('private_lineage.enabled', return_value=False):
                payload = ri.create_receipt(self.root, requirement='acme/backlog#7', source_issue=source,
                    change=change, archived_contract=archive, verification_receipt=archive / 'verification.md')
            path = self.root.parent / (self.root.name + '-' + change + '.json')
            self.addCleanup(path.unlink, missing_ok=True)
            ri.write_receipt(path, payload)
            receipts.append(path)
        (self.root / '.managed-task-state.json').unlink()
        git(self.root, 'switch', 'main')
        slug = ri._candidate_slug('acme/backlog#7')
        wt = self.root / '.claude/worktrees' / slug
        expected = ['one', 'two']
        with mock.patch('private_lineage.enabled', return_value=False):
            first = ri.assemble_candidate(self.root, requirement='acme/backlog#7', base=base, receipt_paths=receipts[:1], expected_changes=expected)
            first_head = ri.compose_candidate(self.root, manifest=first, receipt_paths=receipts[:1], worktree=wt, branch='agent/' + slug)['head']
            manifest = ri.assemble_candidate(self.root, requirement='acme/backlog#7', base=base, receipt_paths=receipts, expected_changes=expected)
            grown = ri.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts, worktree=wt, branch='agent/' + slug)
            self.assertEqual(git(wt, 'merge-base', first_head, grown['head']), first_head)
            self.assertTrue(ri.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts, worktree=wt, branch='agent/' + slug)['resumed'])
            self.assertEqual([child['work_identity'] for child in manifest['children']], ['BR-7/T1', 'BR-7/T2'])
            bodies = claims()
            bodies['acme/backlog#9'] = claims('acme/backlog#9', 'BR-7/T2')['acme/backlog#9']
            bodies['acme/backlog#7']['body'] += '\n<!-- br-child:acme/backlog#9:2 -->'
            bodies['acme/backlog#7']['body'] = bodies['acme/backlog#7']['body'].replace('<!-- requirement-children:end -->', '- [ ] acme/backlog#9\n<!-- requirement-children:end -->')
            fetch = lambda root, repo, num: bodies[f'{repo}#{num}']
            with mock.patch.object(managed_task, 'fetch_issue', side_effect=fetch), mock.patch.object(requirement_intake, 'fetch_issue', side_effect=fetch), mock.patch.object(publish, 'main_root', return_value=self.root):
                path = ri._candidate_manifest_path('acme/backlog#7')
                self.assertEqual(publish.validate_shared_manifest(wt, path), manifest)
                renamed = path.with_name('other.json')
                (wt / renamed).write_text(json.dumps(manifest))
                git(wt, 'add', str(renamed))
                git(wt, 'commit', '-m', 'wrong path fixture')
                with self.assertRaisesRegex(publish.requirement_integration.RequirementIntegrationError, 'candidate branch'):
                    publish.validate_shared_manifest(wt, renamed)
            # Ordinary recovery generations still own the canonical non-generation path.
            (self.root / 'advance').write_text('advance')
            git(self.root, 'add', 'advance')
            git(self.root, 'commit', '-m', 'advance main')
            recovered = ri.assemble_candidate(self.root, requirement='acme/backlog#7', base=git(self.root, 'rev-parse', 'HEAD'), receipt_paths=receipts)
            recovered_slug = ri._candidate_slug('acme/backlog#7', recovered['generation'])
            recovery_wt = self.root / '.claude/worktrees' / recovered_slug
            ri.compose_candidate(self.root, manifest=recovered, receipt_paths=receipts, worktree=recovery_wt, branch='agent/' + recovered_slug)
            with mock.patch.object(managed_task, 'fetch_issue', side_effect=fetch), mock.patch.object(requirement_intake, 'fetch_issue', side_effect=fetch), mock.patch.object(publish, 'main_root', return_value=self.root):
                self.assertEqual(publish.validate_shared_manifest(recovery_wt, path), recovered)

    def test_shared_identity_is_bound_to_exact_archived_head_and_live_claims(self):
        git(self.root, 'init', '-b', 'main')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'user.name', 'Test')
        archive = self.root / 'openspec/changes/archive/2026-10-04-one'
        archive.mkdir(parents=True)
        (archive / '.managed-task.json').write_text(json.dumps({'source_issue': 'acme/backlog#8', 'change': 'one', 'work_identity': 'BR-7/T1'}))
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'synthetic child')
        manifest = {'requirement': 'acme/backlog#7', 'children': [{'source_issue': 'acme/backlog#8', 'change': 'one', 'head': git(self.root, 'rev-parse', 'HEAD')}]}
        bodies = claims()
        with mock.patch.object(managed_task, 'fetch_issue', side_effect=lambda root, repo, num: bodies[f'{repo}#{num}']):
            self.assertEqual(ri.publication_identities(self.root, manifest), ('BR-7', ['BR-7/T1']))
            manifest['children'][0]['work_identity'] = 'BR-7/T2'
            with self.assertRaisesRegex(ri.RequirementIntegrationError, 'canonical claims'):
                ri.publication_identities(self.root, manifest)
        import private_lineage
        (archive / '.managed-task.json').write_text(json.dumps({'private_lineage_handle': 'pln_' + '1' * 32, 'change': 'one', 'work_identity': 'BR-7/T1'}))
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'synthetic opaque provenance')
        manifest['children'][0].update(head=git(self.root, 'rev-parse', 'HEAD'), work_identity='BR-7/T1')
        with mock.patch.object(managed_task, 'fetch_issue', side_effect=lambda root, repo, num: bodies[f'{repo}#{num}']), \
             mock.patch.object(private_lineage, 'require_handle') as lineage:
            self.assertEqual(ri.publication_identities(self.root, manifest), ('BR-7', ['BR-7/T1']))
        lineage.assert_called_once_with(self.root, 'acme/backlog#8', 'one', 'pln_' + '1' * 32)
        with mock.patch.object(private_lineage, 'require_handle', side_effect=private_lineage.PrivateLineageError('unauthorized lineage')):
            with self.assertRaisesRegex(ri.RequirementIntegrationError, 'unauthorized lineage'):
                ri.publication_identities(self.root, manifest)


if __name__ == '__main__':
    unittest.main()
