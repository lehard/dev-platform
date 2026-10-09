"""Require review when platform scripts gain a direct file-creation call.

This is a source review gate, not a proof about arbitrary Python or editors.
The baseline records existing call sites; a new site must use the checked
shared writer or receive an explicit baseline review in the same change.
"""
from __future__ import annotations

import ast
import collections
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"


def creation_calls(scripts: Path = SCRIPTS) -> collections.Counter[str]:
    found: collections.Counter[str] = collections.Counter()
    for source in sorted(scripts.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

        class Visit(ast.NodeVisitor):
            scopes: list[str] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.scopes.append(node.name)
                self.generic_visit(node)
                self.scopes.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node: ast.Call) -> None:
                target = node.func
                name = target.attr if isinstance(target, ast.Attribute) else target.id if isinstance(target, ast.Name) else ""
                direct = name in {
                    "write_text", "write_bytes", "touch", "mkstemp", "NamedTemporaryFile",
                    "copyfile", "copy2", "move",
                }
                if name == "copy" and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "shutil":
                    direct = True
                if name in {"replace", "rename"} and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "os":
                    direct = True
                if name == "open":
                    os_open = isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "os"
                    if os_open:
                        direct = True  # flags can be computed; review every new os.open call
                    else:
                        index = 0 if isinstance(target, ast.Attribute) else 1
                        mode = node.args[index] if len(node.args) > index else None
                        if mode is None:
                            mode = next((item.value for item in node.keywords if item.arg == "mode"), None)
                        direct = isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wax+")
                if direct:
                    found[f"{source.name}:{'.'.join(self.scopes) or '<module>'}:{name}"] += 1
                self.generic_visit(node)

        Visit().visit(tree)
    return found


# Existing direct creation sites, reviewed when this guard was introduced.
# Keep the counts exact: adding a call inside an existing function also fails.
REVIEWED_BASELINE: dict[str, int] = {
    # Machine pool: machine-local slot/queue files outside the repository, created with an explicit
    # cross-account mode (fchmod 0o666) rather than shared-workspace semantics; reads only lock and inspect.
    'machine_pool.py:_open_shared:open': 1,
    'machine_pool.py:_scan_queue:open': 1,
    'machine_pool.py:read_holders:open': 1,
    # Trusted harness manifests/evidence and private reviewer scratch inputs.
    'requirement_composition.py:execute_composition_review:write_text': 4,
    'requirement_composition.py:run_child_review:write_text': 2,
    'requirement_contributions.py:write_manifest:write_text': 1,
    '_platform_common.py:atomic_write_text:mkstemp': 1,
    '_platform_common.py:atomic_write_text:replace': 1,
    '_platform_common.py:locked_json:open': 1,
    'agent_doctor.py:ensure_git_hooks:write_bytes': 1,
    'agent_friction.py:cmd_promote:NamedTemporaryFile': 1,
    'agent_friction.py:append_coordinator_event:open': 1,
    'agent_friction.py:cmd_record:open': 1,
    'agent_friction.py:friction_lock:open': 1,
    'browser_verification.py:main:write_text': 1,
    'browser_verification.py:record_run:write_text': 1,
    'capability_evals.py:main:write_text': 1,
    'capability_manager.py:sync:write_text': 1,
    'capability_manager.py:write_selection:write_text': 1,
    'capability_manager.py:create_from_descriptor:copyfile': 2,
    'delegated_write_guard.py:_write_writer_state:open': 1,
    'delegated_write_guard.py:_write_writer_state:replace': 1,
    'delegated_write_guard.py:acquire:open': 1,
    'delegated_write_guard.py:write_claude_guard:write_text': 2,
    'dev.py:ensure_local_generated_excludes:open': 1,
    'dev.py:refresh_openspec:write_text': 1,
    'disposable_repository_sandbox.py:create:write_text': 1,
    'harness_replay.py:isolated_workspace:write_text': 1,
    'harness_replay.py:main:write_text': 1,
    # Disposable LLM checkout and its scratch HOME live in a private worker temp directory.
    'lifecycle_workers.py:import_worktree:copyfile': 1,
    'lifecycle_workers.py:prepare_checkout:open': 1,
    'lifecycle_workers.py:scratch_home:copy2': 1,
    # Reviewer schema and candidate diff go to a private temporary directory outside the repository.
    'independent_review_runner.py:run_review:write_text': 2,
    'integration_state.py:local_state_matches_remote_target:mkstemp': 1,
    'integration_state.py:serialized_integration:open': 1,
    # Operator-local generated artifacts: atomic, explicit modes, cooperative generated-state replacement.
    # _open uses no-follow descriptors (read-only, write-only fallback for owner-created 0200 sources) for bounded repair.
    'local_workspace.py:write:mkstemp': 1,
    'local_workspace.py:write:replace': 1,
    'local_workspace.py:_open:open': 3,
    # The external fleet lock is no-follow, regular/single-link checked and group writable.
    'local_workspace.py:sync:open': 1,
    # Empty owner-local advisory lock in system temp: no-follow, regular/single-link
    # checked; no identity data, registry, integration writes or inode-removal race.
    'managed_work_identity.py:allocation_lock:open': 1,
    'model_routing.py:delegate_codex_context:write_text': 1,
    'platform_bootstrap.py:ensure_project_context_map:write_text': 1,
    'platform_bootstrap.py:initialize_openspec:write_text': 1,
    'platform_bootstrap.py:sync_operator_integration:write_text': 1,
    'platform_bootstrap.py:sync_platform_version:write_text': 1,
    'repository_goal_scan.py:_write:write_text': 1,
    'requirement_integration.py:compose_candidate:write_text': 1,
    'requirement_integration.py:main:write_text': 1,
    'requirement_integration.py:write_receipt:write_text': 1,
    'requirement_integration.py:_provision_local_contract:copy2': 1,
    'requirement_merge_recovery.py:finalize:write_text': 1,
    'requirement_merge_recovery.py:prepare:write_text': 1,
    'run_test_groups.py:main:write_text': 1,
    'run_test_groups.py:write_git_template:write_text': 2,
    'select_checks.py:write_evidence:write_text': 1,
    'shared_workspace.py:atomic_write_text:mkstemp': 1,
    'shared_workspace.py:atomic_write_text:replace': 1,
    'shared_workspace.py:create_shared_text:open': 1,
    'shared_workspace.py:session_admission_probe:write_text': 1,
    'start_worktree.py:create_worktree:copy2': 1,
}


class SharedWriterGuardTests(unittest.TestCase):
    def test_new_direct_writers_require_review(self) -> None:
        self.assertEqual(dict(creation_calls()), REVIEWED_BASELINE)

    def test_new_function_with_raw_writer_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "future_writer.py"
            source.write_text("def publish(path):\n    path.write_text('raw')\n", encoding="utf-8")
            self.assertEqual(creation_calls(Path(temporary)), {"future_writer.py:publish:write_text": 1})


if __name__ == "__main__":
    unittest.main()
