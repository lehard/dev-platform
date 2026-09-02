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

# A Jara-shaped project-owned publication harness: it neither defines the
# platform `PrRef` type nor `request_protected_merge`. This is exactly the
# surface that broke managed intake for Jara_Fin Backlog #93.
JARA_PROJECT_PUBLISH = '''\
"""Project-owned publication harness preserved by Copier for harness_mode=project."""


def publish(*_args, **_kwargs):
    raise SystemExit("project-owned publication entrypoint")
'''

JARA_FINISH_TASK = '''\
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
        (scripts / "project_publish.py").write_text(JARA_PROJECT_PUBLISH, encoding="utf-8")
        (scripts / "finish_task.py").write_text(JARA_FINISH_TASK, encoding="utf-8")
        return scripts

    def test_standard_start_import_graph_loads_without_platform_publication_api(self) -> None:
        """`import start_task` must succeed against a Jara-shaped project harness."""
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
                "{'main_branch': 'main', 'harness_mode': 'project'}, None);"
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
