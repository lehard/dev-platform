from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"

# The platform-owned modules the standard managed-start entrypoint's import
# graph is allowed to require in *every* harness mode. Deliberately excludes
# project_publish.py / finish_task.py: `_skip_if_exists` (copier.yml) preserves
# those for `harness_mode=project`, so a mature repository is allowed to keep
# them project-owned without the platform publication API.
MANAGED_START_IMPORT_GRAPH = (
    "_platform_common.py",
    "integration_state.py",
    "publication_state.py",
    "rollout_identity.py",
    "rollout_preflight.py",
    "start_worktree.py",
    "start_task.py",
)

# A legacy-shaped project-owned publication harness: it neither defines the
# platform `PrRef` type nor `request_protected_merge`. This is the generic
# shape of a real incident where a mature downstream harness broke managed
# intake because it predated the platform publication API.
LEGACY_PROJECT_PUBLISH = '''\
"""Project-owned publication harness preserved by Copier for harness_mode=project."""


def publish(*_args, **_kwargs):
    raise SystemExit("project-owned publication entrypoint")
'''

LEGACY_FINISH_TASK = '''\
"""Project-owned finish harness without the platform sync helper."""


def finish(*_args, **_kwargs):
    raise SystemExit("project-owned finish entrypoint")
'''


class ManagedIntakeProjectHarnessIsolationTests(unittest.TestCase):
    def _project_scripts(self, tmp: Path) -> Path:
        scripts = tmp / "scripts"
        scripts.mkdir()
        for name in MANAGED_START_IMPORT_GRAPH:
            (scripts / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")
        (scripts / "project_publish.py").write_text(LEGACY_PROJECT_PUBLISH, encoding="utf-8")
        (scripts / "finish_task.py").write_text(LEGACY_FINISH_TASK, encoding="utf-8")
        return scripts

    def test_standard_start_import_graph_loads_without_platform_publication_api(self) -> None:
        """`import start_task` must succeed against a legacy-shaped project harness."""
        with tempfile.TemporaryDirectory(prefix="managed-intake-project-harness-") as tmp:
            scripts = self._project_scripts(Path(tmp))
            probe = (
                "import start_task, rollout_preflight;"
                "pp = __import__('project_publish');"
                "assert not hasattr(pp, 'PrRef'), 'fixture should lack the platform PrRef';"
                "assert not hasattr(pp, 'request_protected_merge'), 'fixture should lack request_protected_merge';"
                "print('standalone-import-ok')"
            )
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=scripts,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(scripts), "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("standalone-import-ok", result.stdout)

    def _start_with_pending_rollout(self, tmp: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        """Run the installed (copied) start_task against a pending green rollout; stdout reports merges."""
        scripts = self._project_scripts(tmp)
        for name in ("agent_doctor.py", "project_sync.py"):
            (scripts / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        root = tmp
        for args in (["init", "-q", "-b", "main"], ["config", "user.name", "t"], ["config", "user.email", "t@example.invalid"]):
            subprocess.run(["git", *args], cwd=root, check=True)
        (root / ".dev-platform.toml").write_text(
            'workflow_profile = "standard"\nharness_mode = "platform"\nmain_branch = "main"\n', encoding="utf-8"
        )
        subprocess.run(["git", "add", ".dev-platform.toml"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
        probe = (
            "import pathlib, sys;"
            "import rollout_preflight as rp, start_task as st;"
            "merged = [];"
            "pr = rp.RolloutPR(7, 'https://example.invalid/pr/7', 'dev-platform/rollout-v9.0.0', 'v9.0.0', 'abc');"
            "rp.observe_pending_rollout = lambda *a, **k: rp.RolloutPreflightResult(rp.SAFE_TO_ADOPT, detail='green', pr=pr);"
            "rp._load_platform_reconciliation_helpers = lambda: None;"
            "rp._merge_rollout_pr = lambda *a, **k: (merged.append(7), ('merged', ''))[1];"
            "rp._synchronize_local_main = lambda *a, **k: (True, '');"
            "st.require_fresh_task_base = lambda *a, **k: 'a' * 40;"
            "st.github_cli_env = lambda root: {};"
            "started = st.start_task(pathlib.Path(sys.argv[1]), 'slug', 'task');"
            "print('merged=' + str(len(merged)) + ' branch=' + started.branch)"
        )
        env = {key: value for key, value in os.environ.items() if key != "DEV_PLATFORM_DEFER_ROLLOUT"}
        return subprocess.run(
            [sys.executable, "-c", probe, str(root)],
            cwd=scripts, capture_output=True, text=True,
            env={**env, **extra_env, "PYTHONPATH": str(scripts), "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_installed_start_leaves_pending_rollout_unmerged_when_session_defers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="managed-intake-project-harness-") as tmp:
            result = self._start_with_pending_rollout(Path(tmp), {"DEV_PLATFORM_DEFER_ROLLOUT": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("merged=0 branch=agent/slug", result.stdout)
        self.assertIn("rollout PR #7 (v9.0.0) was skipped and left unmerged", result.stdout)

    def test_installed_start_without_deferral_still_merges_pending_rollout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="managed-intake-project-harness-") as tmp:
            result = self._start_with_pending_rollout(Path(tmp), {})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("merged=1 branch=agent/slug", result.stdout)

    def test_installed_start_rejects_an_unsupported_deferral_value_before_any_observation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="managed-intake-project-harness-") as tmp:
            result = self._start_with_pending_rollout(Path(tmp), {"DEV_PLATFORM_DEFER_ROLLOUT": "yes"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEV_PLATFORM_DEFER_ROLLOUT", result.stderr)

    def test_read_only_observation_works_against_the_project_harness_fixture(self) -> None:
        """`observe_pending_rollout` (used by agent_doctor for every harness) stays usable."""
        with tempfile.TemporaryDirectory(prefix="managed-intake-project-harness-") as tmp:
            scripts = self._project_scripts(Path(tmp))
            probe = (
                "import rollout_preflight as rp;"
                "r = rp.observe_pending_rollout(__import__('pathlib').Path('/tmp/x'), "
                "{'main_branch': 'main', 'harness_mode': 'project'}, None);"
                "assert r.state == rp.NONE, r;"
                "g = rp.reconcile_pending_rollout(__import__('pathlib').Path('/tmp/x'), "
                "{'main_branch': 'main', 'harness_mode': 'project'}, None, defer=False);"
                "assert g.state == rp.NONE, g;"
                "assert 'harness_mode=project' in g.detail, g.detail;"
                "print('project-harness-gate-ok')"
            )
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=scripts,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(scripts), "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("project-harness-gate-ok", result.stdout)

    def test_rollout_preflight_has_no_toplevel_project_owned_publication_import(self) -> None:
        """Static guard: the managed-start graph must not regain a load-time edge."""
        tree = ast.parse((SCRIPTS / "rollout_preflight.py").read_text(encoding="utf-8"))
        top_level_modules: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                top_level_modules.add(node.module)
            elif isinstance(node, ast.Import):
                top_level_modules.update(alias.name for alias in node.names)
        self.assertNotIn("project_publish", top_level_modules)
        self.assertNotIn("finish_task", top_level_modules)


if __name__ == "__main__":
    unittest.main()
