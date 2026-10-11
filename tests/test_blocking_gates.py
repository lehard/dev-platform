"""Blocking-gate catalog, failure helper and protected-surface negative tests.

`template/dev-platform/blocking-gates.toml` classifies every inventoried blocking platform
check as a platform defect, a recoverable state with a recorded recovery, or a justified hard
stop. These tests fail platform validation when the catalog is malformed, names a test that
does not exist, drifts from the scripts that use `gate_failure`, or when a recovery or option
could disable a protected gate.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from test_platform_divergence import MANIFEST, RECORD_PATH, DivergenceTestCase, hotfix_toml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SCRIPTS = TEMPLATE / "scripts"
CATALOG = TEMPLATE / "dev-platform" / "blocking-gates.toml"
SURFACE = TEMPLATE / "dev-platform" / "protected-surface.toml"
sys.path.insert(0, str(SCRIPTS))

import _platform_common as common  # noqa: E402

REQUIRED_CATEGORIES = (
    "independent-review",
    "protected-publication",
    "worktree-isolation",
    "credentials",
    "routing-provenance-evidence",
    "git-history",
    "immutable-releases",
)
# A recovery step is a recorded step, never a flag or variable that turns a check off.
FORBIDDEN_RECOVERY = re.compile(
    r"--force|--no-verify|--no-checks|--skip|--bypass|--override|--disable|--ignore|--yes\b|--unsafe|_ALLOW_[A-Z_]*=",
    re.IGNORECASE,
)
# An option that switches a gate off for a whole script.
UNIVERSAL_BYPASS_OPTION = re.compile(
    r"^--(force|bypass|override|unsafe|yes|no-verify|no-checks|disable|ignore)(-[a-z0-9-]+)?$|^--skip(-[a-z0-9-]+)?$"
)
# Existing options that match the pattern, each inspected and justified. A new entry needs the same review;
# a stale entry (the option no longer exists) also fails.
ALLOWED_BYPASS_LIKE_OPTIONS = {
    ("template/scripts/finish_task.py", "--no-checks"): (
        "pre-existing operator override of the local check run only (run_checks returns early); refused unless "
        "DEV_PLATFORM_ALLOW_NO_CHECKS=1 is set after an explicit decision; reported as a follow-up for review"
    ),
    ("template/scripts/start_worktree.py", "--skip-sync"): (
        "pre-existing hidden option (argparse.SUPPRESS) that skips only the sync before a worktree is created; "
        "it guards no validation, review or publication gate"
    ),
}
TEST_ID = re.compile(r"(tests/[A-Za-z0-9_]+\.py)::([A-Za-z_][A-Za-z0-9_]*)::(test[A-Za-z0-9_]*)")
RECOVERY_PATH = re.compile(r"(?:scripts|docs|dev-platform)/[A-Za-z0-9_./-]+\.(?:py|md|toml)")


def python_files() -> list[Path]:
    return sorted([*SCRIPTS.rglob("*.py"), *(ROOT / "scripts").glob("*.py")])


def helper_calls(source: str) -> list[tuple[str, ast.Call]]:
    """Every gate_failure / gate_message call as (helper name, node)."""
    calls: list[tuple[str, ast.Call]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name in {"gate_failure", "gate_message"}:
                calls.append((name, node))
    return calls


def helper_ids(source: str) -> list[str | None]:
    """The literal gate id of every helper call in `source`; None where the id is not a string literal."""
    ids: list[str | None] = []
    for _, call in helper_calls(source):
        first = call.args[0] if call.args else None
        ids.append(first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None)
    return ids


def option_flags(source: str) -> set[str]:
    flags: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            flags |= {a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("-")}
    return flags


def resolve_test_id(test_id: str) -> str | None:
    """None when `tests/<file>.py::<Class>::<test>` names a real test method, else why not."""
    match = TEST_ID.fullmatch(test_id)
    if match is None:
        return "not a test id tests/<file>.py::<Class>::<test>"
    path = ROOT / match.group(1)
    if not path.is_file():
        return f"{match.group(1)} does not exist"
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ClassDef) and node.name == match.group(2):
            if any(isinstance(item, ast.FunctionDef) and item.name == match.group(3) for item in node.body):
                return None
            return f"class {match.group(2)} has no method {match.group(3)}"
    return f"{match.group(1)} has no class {match.group(2)}"


def glob_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        char = pattern[index]
        out.append("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char))
        index += 1
    return re.compile("".join(out) + r"\Z")


def classify(path: str) -> str:
    surface = tomllib.loads(SURFACE.read_text(encoding="utf-8"))
    if any(glob_regex(entry["path"]).match(path) for entry in surface["protected"]):
        return "protected"
    if path in surface["hotfixable"]:
        return "hotfixable"
    raise AssertionError(f"{path} is neither protected nor hotfixable in protected-surface.toml")


def gate(gate_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": gate_id, "script": "scripts/x.py", "class": "recoverable", "summary": "s", "migrated": False,
        "rejection_tests": ["tests/test_a.py::A::test_b"], "recovery": "python3 scripts/x.py fix",
        "recovery_tests": ["tests/test_a.py::A::test_c"],
    }
    base.update(overrides)
    return base


def toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def catalog_text(*gates: dict[str, object]) -> str:
    return "".join(
        "[[gate]]\n" + "".join(f"{key} = {toml_value(value)}\n" for key, value in entry.items()) + "\n" for entry in gates
    )


class CatalogFileCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "blocking-gates.toml"

    def write(self, *gates: dict[str, object]) -> Path:
        self.path.write_text(catalog_text(*gates), encoding="utf-8")
        return self.path


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gates = common.load_gate_catalog(CATALOG)

    def test_catalog_is_well_formed_and_every_class_field_is_present(self) -> None:
        self.assertGreaterEqual(len(self.gates), 10)
        for gate_id, entry in self.gates.items():
            with self.subTest(gate=gate_id):
                if entry["class"] == "recoverable":
                    self.assertTrue(entry["recovery"].strip() and entry["recovery_tests"])
                elif entry["class"] == "hard-stop":
                    self.assertTrue(entry["justification"].strip())
                else:
                    self.assertEqual(classify(entry["script"]), entry["hotfix_path"])

    def test_inventory_names_the_gates_the_requirement_lists(self) -> None:
        for gate_id in (
            "routing-early-gate", "delegated-write-containment", "task-freshness", "proven-base-freshness",
            "shared-workspace-admission", "merge-commit-hook", "publication-preflight", "scope-overlap",
            "platform-divergence", "platform-divergence-protected",
        ):
            with self.subTest(gate=gate_id):
                self.assertIn(gate_id, self.gates)

    def test_every_gate_script_exists_in_the_template_and_is_classified(self) -> None:
        for gate_id, entry in self.gates.items():
            with self.subTest(gate=gate_id):
                self.assertTrue((TEMPLATE / entry["script"]).is_file(), f"{gate_id}: script {entry['script']} is not in the template")
                self.assertIn(classify(entry["script"]), {"protected", "hotfixable"})

    def test_every_acceptance_test_resolves_to_a_real_test(self) -> None:
        for gate_id, entry in self.gates.items():
            for field in ("rejection_tests", "recovery_tests"):
                for test_id in entry.get(field, []):
                    with self.subTest(gate=gate_id, field=field, test=test_id):
                        self.assertIsNone(resolve_test_id(test_id), f"{gate_id}: {test_id}")

    def test_every_recovery_names_existing_template_paths(self) -> None:
        for gate_id, entry in self.gates.items():
            if entry["class"] != "recoverable":
                continue
            with self.subTest(gate=gate_id):
                paths = RECOVERY_PATH.findall(entry["recovery"])
                self.assertTrue(paths, f"{gate_id}: recovery names no script or document: {entry['recovery']}")
                for path in paths:
                    self.assertTrue((TEMPLATE / path).is_file(), f"{gate_id}: recovery names missing {path}")

    def test_the_scan_flags_uncataloged_and_non_literal_gate_ids(self) -> None:
        source = (
            "from _platform_common import gate_failure\n"
            "def f(x):\n"
            "    raise gate_failure('invented-gate', 'blocked', SystemExit)\n"
            "def g(x):\n"
            "    raise gate_failure(x, 'blocked', SystemExit)\n"
        )
        self.assertEqual(["invented-gate", None], helper_ids(source))
        self.assertNotIn("invented-gate", self.gates)

    def test_migrated_flag_matches_the_scripts_that_use_the_helper(self) -> None:
        used: dict[str, set[str]] = {}
        for path in python_files():
            if path.name == "_platform_common.py":
                continue
            for _, call in helper_calls(path.read_text(encoding="utf-8")):
                first = call.args[0] if call.args else None
                self.assertTrue(
                    isinstance(first, ast.Constant) and isinstance(first.value, str),
                    f"{path.relative_to(ROOT)}:{call.lineno}: the gate id must be a string literal naming a cataloged gate",
                )
                used.setdefault(first.value, set()).add(path.relative_to(TEMPLATE).as_posix() if path.is_relative_to(TEMPLATE) else path.relative_to(ROOT).as_posix())
        self.assertFalse(set(used) - set(self.gates), f"helper used with uncataloged gate ids: {sorted(set(used) - set(self.gates))}")
        for gate_id, entry in self.gates.items():
            with self.subTest(gate=gate_id):
                if entry["migrated"]:
                    self.assertEqual({entry["script"]}, used.get(gate_id), f"{gate_id} is migrated but its script does not call the helper with its id")
                else:
                    self.assertNotIn(gate_id, used, f"{gate_id} calls the helper but the catalog says migrated = false")

    def test_helper_calls_pass_the_exception_type_the_gate_already_raised(self) -> None:
        for path in python_files():
            if path.name == "_platform_common.py":
                continue
            for name, call in helper_calls(path.read_text(encoding="utf-8")):
                if name == "gate_failure":
                    given = len(call.args) + len([kw for kw in call.keywords if kw.arg == "exception_type"])
                    self.assertGreaterEqual(given, 3, f"{path.relative_to(ROOT)}:{call.lineno}: gate_failure needs an explicit exception type")


class CatalogValidationTests(CatalogFileCase):
    def assert_rejected(self, gates: list[dict[str, object]], *needles: str) -> None:
        with self.assertRaises(common.BlockingGateCatalogError) as raised:
            common.load_gate_catalog(self.write(*gates))
        for needle in needles:
            self.assertIn(needle, str(raised.exception))

    def test_a_consistent_catalog_loads(self) -> None:
        loaded = common.load_gate_catalog(self.write(
            gate("a-gate"),
            {"id": "b-gate", "script": "scripts/y.py", "class": "hard-stop", "summary": "s", "migrated": True,
             "rejection_tests": ["tests/test_a.py::A::test_b"], "justification": "intentional"},
            {"id": "c-gate", "script": "scripts/z.py", "class": "platform-defect", "summary": "s", "migrated": False,
             "rejection_tests": ["tests/test_a.py::A::test_b"], "hotfix_path": "protected"},
        ))
        self.assertEqual(["a-gate", "b-gate", "c-gate"], list(loaded))

    def test_recoverable_entry_without_recovery_tests_fails_naming_the_gate(self) -> None:
        entry = gate("no-recovery-test")
        del entry["recovery_tests"]
        self.assert_rejected([entry], "no-recovery-test", "recovery_tests")

    def test_recoverable_entry_with_empty_recovery_tests_or_recovery_fails(self) -> None:
        self.assert_rejected([gate("empty-tests", recovery_tests=[])], "empty-tests", "recovery_tests")
        self.assert_rejected([gate("blank-recovery", recovery="  ")], "blank-recovery", "recovery")

    def test_hard_stop_entry_needs_a_justification(self) -> None:
        base = {"id": "silent-stop", "script": "scripts/x.py", "class": "hard-stop", "summary": "s", "migrated": False,
                "rejection_tests": ["tests/test_a.py::A::test_b"]}
        self.assert_rejected([base], "silent-stop", "justification")
        self.assert_rejected([{**base, "justification": "  "}], "silent-stop", "justification")

    def test_platform_defect_entry_needs_a_valid_hotfix_path(self) -> None:
        base = {"id": "defect-gate", "script": "scripts/x.py", "class": "platform-defect", "summary": "s", "migrated": False,
                "rejection_tests": ["tests/test_a.py::A::test_b"]}
        self.assert_rejected([base], "defect-gate", "hotfix_path")
        self.assert_rejected([{**base, "hotfix_path": "maybe"}], "defect-gate", "hotfix_path")

    def test_rejection_tests_are_required_for_every_class(self) -> None:
        entry = gate("no-rejection")
        del entry["rejection_tests"]
        self.assert_rejected([entry], "no-rejection", "rejection_tests")
        self.assert_rejected([gate("bad-test-id", rejection_tests=["test_a.py::test_b"])], "bad-test-id", "not a test id")

    def test_ids_classes_fields_and_structure_are_validated(self) -> None:
        self.assert_rejected([gate("dup-gate"), gate("dup-gate")], "dup-gate", "duplicate")
        self.assert_rejected([gate("Bad_Id")], "Bad_Id", "kebab-case")
        self.assert_rejected([gate("odd-class", **{"class": "maybe"})], "odd-class", "class")
        self.assert_rejected([gate("extra-field", unexpected="x")], "extra-field", "unknown")
        self.assert_rejected([gate("no-flag", migrated="yes")], "no-flag", "migrated")
        self.assert_rejected([gate("no-script", script="")], "no-script", "script")

    def test_missing_malformed_or_empty_catalog_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(common.BlockingGateCatalogError, "cannot be read"):
            common.load_gate_catalog(self.path)
        self.path.write_text("[[gate]\n", encoding="utf-8")
        with self.assertRaisesRegex(common.BlockingGateCatalogError, "not valid TOML"):
            common.load_gate_catalog(self.path)
        self.path.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(common.BlockingGateCatalogError, "non-empty"):
            common.load_gate_catalog(self.path)
        self.path.write_text('title = "x"\n', encoding="utf-8")
        with self.assertRaisesRegex(common.BlockingGateCatalogError, "non-empty"):
            common.load_gate_catalog(self.path)

    def test_test_id_resolution_reports_each_kind_of_miss(self) -> None:
        self.assertIsNone(resolve_test_id("tests/test_blocking_gates.py::CatalogTests::test_catalog_is_well_formed_and_every_class_field_is_present"))
        self.assertIn("does not exist", resolve_test_id("tests/test_missing_file.py::A::test_b") or "")
        self.assertIn("has no class", resolve_test_id("tests/test_blocking_gates.py::NoSuchClass::test_b") or "")
        self.assertIn("has no method", resolve_test_id("tests/test_blocking_gates.py::CatalogTests::test_nope") or "")
        self.assertIn("not a test id", resolve_test_id("tests/test_blocking_gates.py::CatalogTests") or "")


class GateHelperTests(CatalogFileCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(
            gate("fixable-gate", recovery="python3 scripts/x.py fix --owner-step"),
            {"id": "stop-gate", "script": "scripts/x.py", "class": "hard-stop", "summary": "s", "migrated": False,
             "rejection_tests": ["tests/test_a.py::A::test_b"], "justification": "the boundary is intentional"},
            {"id": "hotfix-gate", "script": "scripts/x.py", "class": "platform-defect", "summary": "s", "migrated": False,
             "rejection_tests": ["tests/test_a.py::A::test_b"], "hotfix_path": "hotfixable"},
            {"id": "release-gate", "script": "scripts/x.py", "class": "platform-defect", "summary": "s", "migrated": False,
             "rejection_tests": ["tests/test_a.py::A::test_b"], "hotfix_path": "protected"},
        )

    def message(self, gate_id: str, detail: str = "something blocked") -> str:
        return common.gate_message(gate_id, detail, catalog=self.path)

    def test_recoverable_failure_prints_class_detail_and_recovery(self) -> None:
        self.assertEqual(
            "[recoverable] fixable-gate: something blocked\nrecovery: python3 scripts/x.py fix --owner-step",
            self.message("fixable-gate"),
        )

    def test_hard_stop_failure_prints_class_detail_and_justification(self) -> None:
        self.assertEqual(
            "[hard-stop] stop-gate: something blocked\nhard stop: the boundary is intentional", self.message("stop-gate")
        )

    def test_platform_defect_points_at_the_hotfix_flow_or_a_release(self) -> None:
        hotfix = self.message("hotfix-gate")
        self.assertTrue(hotfix.startswith("[platform-defect] hotfix-gate: something blocked\nplatform defect: "))
        self.assertIn("hotfixable", hotfix)
        self.assertIn("local hotfix flow", hotfix)
        release = self.message("release-gate")
        self.assertIn("protected", release)
        self.assertIn("platform release", release)

    def test_multiline_detail_is_kept_verbatim_before_the_class_line(self) -> None:
        self.assertEqual(
            "[recoverable] fixable-gate: first\n- second\nrecovery: python3 scripts/x.py fix --owner-step",
            self.message("fixable-gate", "first\n- second"),
        )

    def test_failure_keeps_the_exception_type_the_gate_already_raised(self) -> None:
        for exception_type in (SystemExit, RuntimeError, common.TaskFreshnessError, ValueError):
            with self.subTest(exception_type=exception_type.__name__):
                failure = common.gate_failure("stop-gate", "blocked", exception_type, catalog=self.path)
                self.assertIs(type(failure), exception_type)
                self.assertIn("[hard-stop] stop-gate: blocked", str(failure.args[0]))

    def test_unknown_id_fails_explicitly_naming_it_and_keeps_the_original_failure(self) -> None:
        with self.assertRaises(common.BlockingGateCatalogError) as raised:
            common.gate_failure("not-cataloged", "the real reason", SystemExit, catalog=self.path)
        self.assertIn("unknown blocking gate not-cataloged", str(raised.exception))
        self.assertIn("the real reason", str(raised.exception))

    def test_missing_or_malformed_catalog_fails_explicitly_instead_of_formatting(self) -> None:
        self.path.write_text("[[gate]\n", encoding="utf-8")
        with self.assertRaisesRegex(common.BlockingGateCatalogError, "unknown blocking gate fixable-gate.*not valid TOML"):
            common.gate_failure("fixable-gate", "blocked", SystemExit, catalog=self.path)
        self.path.unlink()
        with self.assertRaisesRegex(common.BlockingGateCatalogError, "unknown blocking gate fixable-gate.*cannot be read"):
            common.gate_failure("fixable-gate", "blocked", SystemExit, catalog=self.path)

    def run_probe(self, snippet: str) -> subprocess.CompletedProcess[str]:
        code = f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); from _platform_common import gate_failure\n{snippet}"
        return subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_cataloged_failure_exits_non_zero_without_printing_success(self) -> None:
        completed = self.run_probe("raise gate_failure('task-freshness', 'task is behind', SystemExit)")
        self.assertNotEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertTrue(completed.stderr.startswith("[recoverable] task-freshness: task is behind\nrecovery: "), completed.stderr)
        self.assertNotRegex(completed.stderr.lower(), r"passed|success|\bok\b")

    def test_uncataloged_failure_exits_non_zero_naming_the_missing_id(self) -> None:
        completed = self.run_probe("raise gate_failure('invented-gate', 'blocked', SystemExit)")
        self.assertNotEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertIn("unknown blocking gate invented-gate", completed.stderr)


class MergeCommitHookTests(unittest.TestCase):
    """The catalog's `merge-commit-hook` rejection test: the shipped hook really blocks merge commits."""

    HOOK = SCRIPTS / "git_hooks" / "pre-merge-commit"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.main = self.base / "main"
        self.main.mkdir()
        self.git(self.main, "init", "-q", "-b", "main")
        for name, value in (("user.email", "gate@example.invalid"), ("user.name", "Gate")):
            self.git(self.main, "config", name, value)
        self.commit(self.main, "base.txt")
        hook = self.main / ".git" / "hooks" / "pre-merge-commit"
        hook.write_bytes(self.HOOK.read_bytes())
        hook.chmod(0o755)

    def git(self, cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, text=True, capture_output=True, check=check)

    def commit(self, cwd: Path, name: str) -> None:
        (cwd / name).write_text(name + "\n", encoding="utf-8")
        self.git(cwd, "add", name)
        self.git(cwd, "commit", "-q", "-m", name)

    def test_merge_commit_in_a_task_worktree_is_blocked(self) -> None:
        task = self.base / "task"
        self.git(self.main, "worktree", "add", "-q", "-b", "task", str(task))
        self.commit(self.main, "main-change.txt")
        self.commit(task, "task-change.txt")
        before = self.git(task, "rev-parse", "HEAD").stdout
        merged = self.git(task, "merge", "--no-edit", "main", check=False)
        self.assertNotEqual(0, merged.returncode)
        self.assertIn("merge commits in task worktrees are blocked", merged.stderr)
        self.assertEqual(before, self.git(task, "rev-parse", "HEAD").stdout, "a merge commit was created despite the hook")

    def test_merge_commit_in_the_integration_copy_is_blocked(self) -> None:
        self.git(self.main, "checkout", "-q", "-b", "topic")
        self.commit(self.main, "topic-change.txt")
        self.git(self.main, "checkout", "-q", "main")
        self.commit(self.main, "main-change.txt")
        before = self.git(self.main, "rev-parse", "HEAD").stdout
        merged = self.git(self.main, "merge", "--no-edit", "topic", check=False)
        self.assertNotEqual(0, merged.returncode)
        self.assertIn("merge commits in the integration copy are blocked", merged.stderr)
        self.assertEqual(before, self.git(self.main, "rev-parse", "HEAD").stdout)


class ProtectedSurfaceNegativeTests(DivergenceTestCase):
    """Neither a hotfix record nor a cataloged recovery can disable a protected category."""

    @classmethod
    def representative_paths(cls) -> dict[str, str]:
        surface = tomllib.loads(SURFACE.read_text(encoding="utf-8"))
        chosen: dict[str, str] = {}
        for entry in surface["protected"]:
            path, category = entry["path"], entry["category"]
            if category not in chosen and not any(char in path for char in "*?") and path in MANIFEST["files"]:
                chosen[category] = path
        return chosen

    def test_every_required_category_has_a_representative_protected_path(self) -> None:
        self.assertEqual(set(REQUIRED_CATEGORIES), set(self.representative_paths()))

    def test_a_hotfix_record_naming_a_protected_path_of_each_category_is_refused(self) -> None:
        for category, path in self.representative_paths().items():
            with self.subTest(category=category, path=path):
                (self.root / RECORD_PATH).write_text(hotfix_toml(path=path), encoding="utf-8")
                self.assert_fails("protected-touch", path, contains="names a protected path")

    def test_editing_a_protected_file_of_each_category_stays_a_protected_touch_even_with_a_record(self) -> None:
        paths = self.representative_paths()
        for category, path in paths.items():
            self.patch(path)
            self.declare(path=path, platform_version="1.9.5")
        completed = self.run_check()
        self.assertNotEqual(0, completed.returncode, completed.stdout)
        self.assertNotIn("platform_divergence: OK", completed.stdout)
        for category, path in paths.items():
            with self.subTest(category=category, path=path):
                self.assertRegex(completed.stdout, rf"(?m)^\[protected-touch\] {re.escape(path)}: ")

    def test_the_gate_catalog_is_protected_like_the_surface_it_belongs_to(self) -> None:
        catalog = "dev-platform/blocking-gates.toml"
        self.patch(catalog, "# relabel a hard stop\n")
        self.assert_fails("protected-touch", catalog)
        (self.root / RECORD_PATH).write_text(hotfix_toml(path=catalog), encoding="utf-8")
        self.assert_fails("protected-touch", catalog, contains="names a protected path")

    def test_no_cataloged_recovery_contains_a_force_or_check_disabling_flag(self) -> None:
        for gate_id, entry in common.load_gate_catalog(CATALOG).items():
            if entry["class"] == "recoverable":
                with self.subTest(gate=gate_id):
                    self.assertIsNone(FORBIDDEN_RECOVERY.search(entry["recovery"]), entry["recovery"])

    def test_the_recovery_filter_flags_force_and_disabling_flags(self) -> None:
        for recovery in (
            "git push --force", "finish_task.py --no-checks", "git commit --no-verify", "tool --skip-checks",
            "DEV_PLATFORM_ALLOW_MERGE_COMMIT=1 git merge", "tool --bypass-gate", "tool --disable-review",
        ):
            with self.subTest(recovery=recovery):
                self.assertIsNotNone(FORBIDDEN_RECOVERY.search(recovery))
        self.assertIsNone(FORBIDDEN_RECOVERY.search("python3 scripts/model_routing.py approve-supervisor-diff --approval x --reason y"))

    def test_no_script_defines_a_universal_force_or_skip_checks_option(self) -> None:
        found: dict[tuple[str, str], str] = {}
        for path in python_files():
            relative = path.relative_to(ROOT).as_posix()
            for flag in option_flags(path.read_text(encoding="utf-8")):
                if UNIVERSAL_BYPASS_OPTION.match(flag):
                    found[(relative, flag)] = flag
        unreviewed = sorted(set(found) - set(ALLOWED_BYPASS_LIKE_OPTIONS))
        self.assertEqual([], unreviewed, f"option(s) that could switch a gate off need review or removal: {unreviewed}")
        stale = sorted(set(ALLOWED_BYPASS_LIKE_OPTIONS) - set(found))
        self.assertEqual([], stale, f"allowlisted option(s) no longer exist; remove them from the allowlist: {stale}")
        for justification in ALLOWED_BYPASS_LIKE_OPTIONS.values():
            self.assertGreater(len(justification), 40)

    def test_the_option_scan_flags_a_force_option(self) -> None:
        source = "import argparse\np = argparse.ArgumentParser()\np.add_argument('--force', action='store_true')\np.add_argument('--skip-checks')\np.add_argument('--target')\n"
        self.assertEqual({"--force", "--skip-checks", "--target"}, option_flags(source))
        self.assertEqual(["--force", "--skip-checks"], sorted(flag for flag in option_flags(source) if UNIVERSAL_BYPASS_OPTION.match(flag)))


if __name__ == "__main__":
    unittest.main()
