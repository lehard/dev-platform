from __future__ import annotations

import contextlib
import io
import json
import os
import queue
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import isolate_machine_pool_environment, load_platform_module  # noqa: E402

machine_pool = load_platform_module("machine_pool", SCRIPTS / "machine_pool.py")
platform_common = load_platform_module("_platform_common", SCRIPTS / "_platform_common.py")
run_test_groups = load_platform_module("run_test_groups", SCRIPTS / "run_test_groups.py")
select_checks = load_platform_module("select_checks", SCRIPTS / "select_checks.py")
integration = load_platform_module("requirement_integration", SCRIPTS / "requirement_integration.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")
final = load_platform_module("post_review_finalization", SCRIPTS / "post_review_finalization.py")

POOL_ENV = machine_pool.POOL_ENV
LEASE_ENV = machine_pool.LEASE_ENV
CLASS_ENV = machine_pool.CHECK_CLASS_ENV
POOL_VARIABLES = (POOL_ENV, LEASE_ENV, CLASS_ENV)


def setUpModule() -> None:
    isolate_machine_pool_environment()

HELPER = """
import os, signal, subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import machine_pool
mode, weight, check_class, root = sys.argv[2], int(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
hooks = machine_pool.Hooks(poll_interval=0.02, progress_interval=0.1)
with machine_pool.lease(weight, "test", check_class=check_class, root=root, hooks=hooks) as lease:
    print("ACQUIRED", flush=True)
    if mode == "hold":
        sys.stdin.readline()
    elif mode == "orphan":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], pass_fds=lease.fds)
        print("CHILD", child.pid, flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    elif mode == "nested":
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); import machine_pool;"
            "l = machine_pool.lease(1, 'inner').__enter__();"
            "print('NESTED', l.nested, l.weight)"
        )
        done = subprocess.run([sys.executable, "-c", code, sys.argv[1]], capture_output=True, text=True, timeout=20,
                              pass_fds=lease.fds)
        print(done.stdout.strip() + done.stderr.strip(), flush=True)
"""


def clean_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in POOL_VARIABLES}


class FakeClock:
    """A clock whose sleep advances time instantly, so waits finish without real delay."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def fake_hooks(clock: FakeClock, lines: list[str], *, load=lambda: 0.0, memory=lambda: 1e6) -> object:
    return machine_pool.Hooks(monotonic=clock.monotonic, sleep=clock.sleep, poll_interval=1.0, progress_interval=60.0,
                              load_per_cpu=load, available_memory_mb=memory, out=lines.append)


def fast_hooks(lines: list[str] | None = None) -> object:
    sink = [] if lines is None else lines
    return machine_pool.Hooks(poll_interval=0.01, progress_interval=60.0, load_per_cpu=lambda: 0.0,
                              available_memory_mb=lambda: 1e6, out=sink.append)


class PoolFixture(unittest.TestCase):
    # Unit tests inject load/memory readers; these defaults are compared against injected values.
    MAX_LOAD_PER_CPU = 2.0
    MIN_AVAILABLE_MEMORY_MB = 512
    TOKENS = 3

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.directory = self.base / "pool"
        self.directory.mkdir()
        self.config_path = self.write_config()
        self.environ = {POOL_ENV: str(self.config_path)}
        self.config = machine_pool.load_config(self.environ)
        patcher = mock.patch.object(machine_pool, "_git_branch", return_value="task-branch")
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_config(self, **overrides: object) -> Path:
        values: dict[str, object] = {
            "directory": str(self.directory), "tokens": self.TOKENS, "wait_timeout_seconds": 200,
            "max_load_per_cpu": self.MAX_LOAD_PER_CPU, "min_available_memory_mb": self.MIN_AVAILABLE_MEMORY_MB,
        }
        values.update(overrides)
        lines = [f"{key} = {json.dumps(value)}" for key, value in values.items() if value is not None]
        path = self.base / "pool.toml"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def process_environment(self) -> dict[str, str]:
        env = clean_environment()
        env[POOL_ENV] = str(self.config_path)
        return env

    def spawn(self, mode: str, weight: int, check_class: str = "development") -> "Child":
        return Child(subprocess.Popen(
            [sys.executable, "-c", HELPER, str(SCRIPTS), mode, str(weight), check_class, str(ROOT)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env=self.process_environment()))

    def queue_names(self) -> list[str]:
        try:
            return sorted(os.listdir(self.config.queue))
        except FileNotFoundError:
            return []

    def wait_until(self, predicate, what: str, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail(f"timed out waiting for {what}")


class Child:
    """A helper process with a reader thread so output waits have a timeout."""

    def __init__(self, process: subprocess.Popen) -> None:
        self.process = process
        self.lines: queue.Queue[str] = queue.Queue()
        self.seen: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.process.stdout:
            self.lines.put(line.rstrip("\n"))

    def wait_for(self, prefix: str, timeout: float = 20.0) -> str:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"no line starting with {prefix!r}; saw {self.seen}")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                continue
            self.seen.append(line)
            if line.startswith(prefix):
                return line

    def release(self) -> None:
        self.process.stdin.write("go\n")
        self.process.stdin.flush()
        self.process.wait(timeout=20)

    def kill(self) -> None:
        self.process.kill()
        self.process.wait(timeout=20)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=20)
        self.process.stdin.close()


class ConfigurationTests(PoolFixture):
    def test_unset_variable_is_the_declared_unpooled_mode(self) -> None:
        self.assertIsNone(machine_pool.load_config({}))

    def test_valid_configuration_is_parsed(self) -> None:
        self.assertEqual((self.config.tokens, self.config.wait_timeout_seconds, self.config.max_load_per_cpu,
                          self.config.min_available_memory_mb, self.config.directory),
                         (3, 200, 2.0, 512, self.directory))

    def expect_error(self, pattern: str, environ: dict[str, str] | None = None) -> None:
        with self.assertRaisesRegex(machine_pool.PoolConfigError, pattern):
            machine_pool.load_config(self.environ if environ is None else environ)

    def test_set_but_empty_relative_or_missing_file_fails(self) -> None:
        self.expect_error("set but empty", {POOL_ENV: " "})
        self.expect_error("absolute path", {POOL_ENV: "pool.toml"})
        self.expect_error("not an existing file", {POOL_ENV: str(self.base / "absent.toml")})

    def test_unparseable_file_fails_naming_it(self) -> None:
        self.config_path.write_text("tokens = [", encoding="utf-8")
        self.expect_error(f"{self.config_path}.*cannot be read")

    def test_missing_and_unknown_keys_fail_naming_them(self) -> None:
        self.config_path.write_text('directory = "/tmp"\n', encoding="utf-8")
        self.expect_error("missing required key.*tokens.*wait_timeout_seconds")
        self.write_config(surprise=1)
        self.expect_error("unknown key.*surprise")

    def test_badly_typed_or_non_positive_values_fail_naming_the_key(self) -> None:
        for key, value in (("tokens", "3"), ("tokens", True), ("tokens", 0), ("tokens", 2.5),
                           ("wait_timeout_seconds", -1), ("min_available_memory_mb", "x"),
                           ("max_load_per_cpu", "high"), ("max_load_per_cpu", 0), ("max_load_per_cpu", True),
                           ("directory", 5), ("directory", "relative/pool")):
            with self.subTest(key=key, value=value):
                self.write_config(**{key: value})
                self.expect_error(key)

    def test_missing_or_non_directory_pool_directory_fails(self) -> None:
        self.write_config(directory=str(self.base / "absent"))
        self.expect_error("not an existing directory")
        (self.base / "file").write_text("x", encoding="utf-8")
        self.write_config(directory=str(self.base / "file"))
        self.expect_error("not an existing directory")

    def test_non_finite_load_limits_fail_naming_the_key(self) -> None:
        for value in ("nan", "+nan", "-nan", "inf", "+inf", "-inf"):
            with self.subTest(value=value):
                self.write_config()
                text = self.config_path.read_text(encoding="utf-8")
                self.config_path.write_text(text.replace("max_load_per_cpu = 2.0", f"max_load_per_cpu = {value}"),
                                            encoding="utf-8")
                self.expect_error("max_load_per_cpu")

    @unittest.skipIf(os.geteuid() == 0, "root bypasses directory permissions")
    def test_unwritable_directory_fails(self) -> None:
        self.directory.chmod(0o555)
        self.addCleanup(self.directory.chmod, 0o755)
        self.expect_error("not readable and writable")

    def test_unknown_class_fails_with_and_without_a_pool(self) -> None:
        for environ in ({CLASS_ENV: "bogus"}, {POOL_ENV: str(self.config_path), CLASS_ENV: "bogus"}):
            with self.subTest(environ=sorted(environ)), self.assertRaisesRegex(machine_pool.PoolError, "unknown check class 'bogus'"):
                with machine_pool.lease(1, "t", environ=dict(environ), hooks=fast_hooks()):
                    self.fail("must not run")
        with self.assertRaisesRegex(machine_pool.PoolError, "unknown check class 'nope'"):
            with machine_pool.lease(1, "t", check_class="nope", environ=dict(self.environ), hooks=fast_hooks()):
                self.fail("must not run")

    def test_absent_class_means_development_by_contract(self) -> None:
        self.assertEqual(machine_pool.resolve_class({}), "development")
        self.assertEqual(machine_pool.resolve_class({CLASS_ENV: "finalize"}), "finalize")


class LeaseTests(PoolFixture):
    def test_not_configured_prints_the_declared_line_once_and_nested_stays_silent(self) -> None:
        lines: list[str] = []
        environ: dict[str, str] = {}
        with machine_pool.lease(2, "t", environ=environ, hooks=fast_hooks(lines)) as outer:
            self.assertEqual((outer.pooled, outer.weight, outer.nested), (False, None, False))
            self.assertIn(LEASE_ENV, environ)
            with machine_pool.lease(2, "t", environ=environ, hooks=fast_hooks(lines)) as inner:
                self.assertTrue(inner.nested)
                self.assertIsNone(inner.weight)
        self.assertEqual(lines, ["DEV_PLATFORM_MACHINE_POOL: not configured"])
        self.assertNotIn(LEASE_ENV, environ)

    def test_acquire_export_and_release(self) -> None:
        lines: list[str] = []
        environ = dict(self.environ)
        with machine_pool.lease(2, "unit", environ=environ, hooks=fast_hooks(lines)) as lease:
            self.assertEqual((lease.weight, lease.pooled, lease.nested, len(lease.fds)), (2, True, False, 2))
            exported = json.loads(environ[LEASE_ENV])
            self.assertEqual((exported["id"], exported["weight"], exported["pooled"]), (lease.id, 2, True))
            holders = machine_pool.read_holders(self.config)
            self.assertEqual(len(holders), 1)
            self.assertEqual((holders[0]["weight"], holders[0]["class"], holders[0]["branch"], holders[0]["slots"]),
                             (2, "development", "task-branch", [0, 1]))
            self.assertEqual(holders[0]["project_root"], str(Path.cwd().resolve()))
            self.assertEqual(holders[0]["pid"], os.getpid())
        self.assertNotIn(LEASE_ENV, environ)
        self.assertEqual(machine_pool.read_holders(self.config), [])
        self.assertEqual(self.queue_names(), [])
        self.assertTrue(any("acquired 2 of 3 token(s)" in line for line in lines), lines)

    def test_weight_above_tokens_is_capped_only_when_bounded(self) -> None:
        with machine_pool.lease(9, "t", bounded=True, environ=dict(self.environ), hooks=fast_hooks()) as lease:
            self.assertEqual(lease.weight, 3)
        with self.assertRaisesRegex(machine_pool.PoolError, "exceeds the 3 configured"):
            with machine_pool.lease(9, "t", environ=dict(self.environ), hooks=fast_hooks()):
                self.fail("must not run")
        with self.assertRaisesRegex(machine_pool.PoolError, "positive integer"):
            with machine_pool.lease(0, "t", environ=dict(self.environ), hooks=fast_hooks()):
                self.fail("must not run")

    def test_busy_pool_is_all_or_nothing_and_timeout_names_the_holders(self) -> None:
        lines: list[str] = []
        with machine_pool.lease(2, "holder", environ=dict(self.environ), hooks=fast_hooks()):
            with self.assertRaises(machine_pool.PoolTimeout) as caught:
                with machine_pool.lease(2, "waiter", environ=dict(self.environ), hooks=fake_hooks(FakeClock(), lines)):
                    self.fail("must not run")
            message = str(caught.exception)
            self.assertIn("timed out after 200s", message)
            self.assertIn("branch=task-branch", message)
            self.assertIn("class=development", message)
            self.assertIn("fewer than 2 free token(s)", message)
            # The one free token was never kept by the failed all-or-nothing attempt.
            spare = machine_pool._try_take_slots(self.config, 1)
            self.assertIsNotNone(spare)
            os.close(spare[0][0])
        self.assertEqual(self.queue_names(), [])
        self.assertTrue(any("queue position 1 of 1" in line and "holders:" in line for line in lines), lines)

    def test_progress_is_reported_at_start_and_every_sixty_seconds(self) -> None:
        lines: list[str] = []
        clock = FakeClock()
        self.write_config(wait_timeout_seconds=1000)
        config = machine_pool.load_config(self.environ)
        self.assertEqual(config.wait_timeout_seconds, 1000)
        load = lambda: 9.0 if clock.now < 130 else 0.1  # noqa: E731
        with machine_pool.lease(1, "t", environ=dict(self.environ), hooks=fake_hooks(clock, lines, load=load)):
            pass
        waiting = [line for line in lines if "waiting for" in line]
        self.assertEqual(len(waiting), 3, lines)
        self.assertIn("load per CPU 9.00 exceeds the limit 2", waiting[0])
        self.assertTrue(any("acquired 1 of 3" in line for line in lines))

    def test_memory_below_the_minimum_waits_and_unmeasurable_memory_fails(self) -> None:
        lines: list[str] = []
        clock = FakeClock()
        memory = lambda: 100.0 if clock.now < 5 else 2048.0  # noqa: E731
        with machine_pool.lease(1, "t", environ=dict(self.environ), hooks=fake_hooks(clock, lines, memory=memory)):
            pass
        self.assertTrue(any("available memory 100 MB is below the minimum 512 MB" in line for line in lines), lines)

        def unmeasurable() -> float:
            raise machine_pool.PoolError("cannot measure available memory: test")

        with self.assertRaisesRegex(machine_pool.PoolError, "cannot measure available memory"):
            with machine_pool.lease(1, "t", environ=dict(self.environ), hooks=fake_hooks(FakeClock(), [], memory=unmeasurable)):
                self.fail("must not run")
        self.assertEqual(self.queue_names(), [])

    def test_load_and_memory_that_never_clear_time_out_without_running(self) -> None:
        with self.assertRaisesRegex(machine_pool.PoolTimeout, "load per CPU 9.00"):
            with machine_pool.lease(1, "t", environ=dict(self.environ),
                                    hooks=fake_hooks(FakeClock(), [], load=lambda: 9.0)):
                self.fail("must not run")

    def test_nested_acquisition_reuses_the_parent_lease_and_acquires_nothing(self) -> None:
        self.write_config(tokens=1)
        environ = {POOL_ENV: str(self.config_path)}
        config = machine_pool.load_config(environ)
        with machine_pool.lease(1, "outer", environ=environ, hooks=fast_hooks()) as outer:
            # With every token held, a second acquisition would only time out.
            with machine_pool.lease(5, "inner", environ=environ, hooks=fake_hooks(FakeClock(), [])) as inner:
                self.assertTrue(inner.nested)
                self.assertEqual((inner.id, inner.weight, inner.fds), (outer.id, 1, outer.fds))
            self.assertEqual(len(machine_pool.read_holders(config)), 1)
            self.assertEqual(json.loads(environ[LEASE_ENV])["id"], outer.id)
        self.assertEqual(machine_pool.read_holders(config), [])

    def test_invalid_exported_lease_fails(self) -> None:
        for value in ("not json", "[]", json.dumps({"id": "x", "pooled": True}), json.dumps({"id": 1, "pooled": False})):
            with self.subTest(value=value), self.assertRaisesRegex(machine_pool.PoolError, LEASE_ENV):
                with machine_pool.lease(1, "t", environ={LEASE_ENV: value}, hooks=fast_hooks()):
                    self.fail("must not run")

    def test_nested_lease_fails_naming_every_missing_descriptor(self) -> None:
        with machine_pool.lease(1, "outer", environ=dict(self.environ), hooks=fast_hooks()) as outer:
            # Obtain closed descriptor numbers after the parent's files have opened.
            missing = os.pipe()
            for fd in missing:
                os.close(fd)
            for fds in (list(missing), [outer.fds[0], *missing]):
                with self.subTest(fds=fds):
                    environ = {LEASE_ENV: json.dumps({"id": outer.id, "pooled": True,
                                                     "weight": len(fds), "fds": fds})}
                    with self.assertRaises(machine_pool.PoolError) as caught:
                        with machine_pool.lease(1, "inner", environ=environ, hooks=fast_hooks()):
                            self.fail("must not run with missing descriptors")
                    self.assertIn(LEASE_ENV, str(caught.exception))
                    for fd in missing:
                        self.assertIn(str(fd), str(caught.exception))

    def test_nested_process_without_pass_fds_fails(self) -> None:
        environ = self.process_environment()
        with machine_pool.lease(2, "outer", environ=environ, hooks=fast_hooks()) as outer:
            code = (
                "import sys; sys.path.insert(0, sys.argv[1]); import machine_pool;"
                "machine_pool.lease(1, 'inner').__enter__()"
            )
            done = subprocess.run([sys.executable, "-c", code, str(SCRIPTS)], env=environ,
                                  capture_output=True, text=True, timeout=20)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("PoolError", done.stderr)
            self.assertIn(LEASE_ENV, done.stderr)
            for fd in outer.fds:
                self.assertIn(str(fd), done.stderr)

    def test_files_are_usable_by_other_accounts_whatever_the_umask(self) -> None:
        previous = os.umask(0o077)
        self.addCleanup(os.umask, previous)
        with machine_pool.lease(1, "t", environ=dict(self.environ), hooks=fast_hooks()):
            self.assertEqual((self.directory / "slot-0.lock").stat().st_mode & 0o666, 0o666)
            self.assertEqual(self.config.queue.stat().st_mode & 0o777, 0o777)

    @unittest.skipIf(os.geteuid() == 0, "root bypasses file permissions")
    def test_permission_error_names_the_file(self) -> None:
        slot = self.directory / "slot-0.lock"
        slot.write_text("", encoding="utf-8")
        slot.chmod(0o400)
        with self.assertRaisesRegex(machine_pool.PoolError, "slot-0.lock"):
            with machine_pool.lease(1, "t", environ=dict(self.environ), hooks=fast_hooks()):
                self.fail("must not run")

    def test_stale_slot_content_is_ignored_when_the_lock_is_free(self) -> None:
        (self.directory / "slot-0.lock").write_text(json.dumps({"lease": "old", "user": "gone"}), encoding="utf-8")
        self.assertEqual(machine_pool.read_holders(self.config), [])


class QueueOrderTests(PoolFixture):
    TOKENS = 1

    def test_finalize_is_admitted_before_development_and_arrival_order_holds_within_a_class(self) -> None:
        order: list[str] = []
        threads: list[threading.Thread] = []

        def run(name: str, check_class: str) -> None:
            with machine_pool.lease(1, name, check_class=check_class, environ=dict(self.environ), hooks=fast_hooks()):
                order.append(name)

        with machine_pool.lease(1, "holder", environ=dict(self.environ), hooks=fast_hooks()):
            for position, (name, check_class) in enumerate((("dev-1", "development"), ("dev-2", "development"),
                                                            ("fin", "finalize")), 1):
                thread = threading.Thread(target=run, args=(name, check_class))
                thread.start()
                threads.append(thread)
                self.wait_until(lambda: len(self.queue_names()) == position, f"ticket {position}")
        for thread in threads:
            thread.join(timeout=20)
            self.assertFalse(thread.is_alive())
        self.assertEqual(order, ["fin", "dev-1", "dev-2"])
        self.assertEqual(self.queue_names(), [])

    def test_dead_tickets_are_removed_only_after_their_lock_is_taken(self) -> None:
        machine_pool._ensure_queue(self.config)
        dead = self.config.queue / "1-00000000000000000001-4242-abcd1234.json"
        dead.write_text("{}", encoding="utf-8")
        live = self.config.queue / "1-00000000000000000002-4243-abcd1235.json"
        live_fd = os.open(live, os.O_CREAT | os.O_RDWR, 0o666)
        self.addCleanup(os.close, live_fd)
        machine_pool.fcntl.flock(live_fd, machine_pool.fcntl.LOCK_EX | machine_pool.fcntl.LOCK_NB)
        self.assertEqual(machine_pool._scan_queue(self.config, remove_dead=False),
                         [(dead.name, False), (live.name, True)])
        self.assertTrue(dead.exists())  # read-only scan keeps it
        self.assertEqual(machine_pool._scan_queue(self.config, remove_dead=True), [(live.name, True)])
        self.assertFalse(dead.exists())
        self.assertTrue(live.exists())

    def test_foreign_entry_in_the_queue_directory_fails(self) -> None:
        machine_pool._ensure_queue(self.config)
        (self.config.queue / "stray.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(machine_pool.PoolError, "stray.txt"):
            machine_pool._scan_queue(self.config, remove_dead=True)


class ProcessTests(PoolFixture):
    # Real child processes measure the host; admission must never depend on how busy the test machine is.
    MAX_LOAD_PER_CPU = 1_000_000.0
    MIN_AVAILABLE_MEMORY_MB = 1
    TOKENS = 2

    def tearDown(self) -> None:
        for child in getattr(self, "children", []):
            child.close()

    def start(self, mode: str, weight: int, check_class: str = "development") -> Child:
        child = self.spawn(mode, weight, check_class)
        self.children = getattr(self, "children", []) + [child]
        return child

    def test_killed_holder_frees_its_tokens(self) -> None:
        holder = self.start("hold", 2)
        holder.wait_for("ACQUIRED")
        self.assertEqual(sum(len(h["slots"]) for h in machine_pool.read_holders(self.config)), 2)
        holder.kill()
        self.assertEqual(machine_pool.read_holders(self.config), [])
        with machine_pool.lease(2, "after", environ=dict(self.environ), hooks=fast_hooks()) as lease:
            self.assertEqual(lease.weight, 2)

    def test_waiter_starts_when_the_holder_exits(self) -> None:
        holder = self.start("hold", 2)
        holder.wait_for("ACQUIRED")
        waiter = self.start("hold", 1)
        line = waiter.wait_for("DEV_PLATFORM_MACHINE_POOL: waiting")
        self.assertIn("queue position 1 of 1", line)
        self.assertIn("branch=", line)
        holder.release()
        waiter.wait_for("ACQUIRED")
        waiter.release()

    def test_killed_waiter_leaves_a_dead_ticket_the_next_waiter_removes(self) -> None:
        holder = self.start("hold", 2)
        holder.wait_for("ACQUIRED")
        waiter = self.start("hold", 1)
        waiter.wait_for("DEV_PLATFORM_MACHINE_POOL: waiting")
        self.assertEqual(len(self.queue_names()), 1)
        waiter.kill()
        self.assertEqual(len(self.queue_names()), 1)
        self.assertEqual([alive for _, alive in machine_pool._scan_queue(self.config, remove_dead=False)], [False])
        self.assertIn("dead tickets awaiting removal", machine_pool.status_text(self.config, fast_hooks()))
        holder.release()
        with machine_pool.lease(1, "after", environ=dict(self.environ), hooks=fast_hooks()):
            pass
        self.assertEqual(self.queue_names(), [])

    def test_orphaned_child_keeps_the_tokens_through_inherited_descriptors(self) -> None:
        holder = self.start("orphan", 2)
        holder.wait_for("ACQUIRED")
        child_pid = int(holder.wait_for("CHILD").split()[1])
        holder.process.wait(timeout=20)  # the leasing process died (SIGKILL); its child lives on
        self.assertEqual(holder.process.returncode, -signal.SIGKILL)
        try:
            self.assertEqual(sum(len(h["slots"]) for h in machine_pool.read_holders(self.config)), 2)
            with self.assertRaises(machine_pool.PoolTimeout):
                with machine_pool.lease(1, "blocked", environ=dict(self.environ),
                                        hooks=fake_hooks(FakeClock(), [])):
                    self.fail("tokens must still be held by the orphan")
        finally:
            os.kill(child_pid, signal.SIGKILL)
        self.wait_until(lambda: machine_pool.read_holders(self.config) == [], "orphan tokens to be released")

    def test_child_process_of_a_lease_reuses_it(self) -> None:
        nested = self.start("nested", 2)
        nested.wait_for("ACQUIRED")
        line = nested.wait_for("NESTED")
        self.assertEqual(line, "NESTED True 2")  # the pool has only 2 tokens, all held by the parent

    def test_status_reports_configuration_holders_waiters_and_load(self) -> None:
        holder = self.start("hold", 1)
        holder.wait_for("ACQUIRED")
        waiter = self.start("hold", 2, "finalize")
        waiter.wait_for("DEV_PLATFORM_MACHINE_POOL: waiting")
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "machine_pool.py"), "status"], capture_output=True,
                              text=True, env=self.process_environment())
        self.assertEqual(done.returncode, 0, done.stderr)
        output = done.stdout
        self.assertIn(f"{POOL_ENV}: {self.config_path}", output)
        self.assertIn("tokens: 2 (held 1, free 1)", output)
        self.assertIn("max_load_per_cpu: 1e+06; current load per CPU:", output)
        self.assertIn("min_available_memory_mb: 1; current available memory MB:", output)
        self.assertIn("class=development weight=1", output)
        self.assertIn("1. ", output.split("waiters:")[1])
        self.assertIn("class=finalize weight=2", output.split("waiters:")[1])
        self.assertEqual(len(self.queue_names()), 1)  # status removed nothing
        holder.release()
        waiter.wait_for("ACQUIRED")
        waiter.release()

    def test_status_when_not_configured_and_when_misconfigured(self) -> None:
        script = str(ROOT / "scripts" / "machine_pool.py")
        done = subprocess.run([sys.executable, script, "status"], capture_output=True, text=True, env=clean_environment())
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "DEV_PLATFORM_MACHINE_POOL: not configured"))
        bad = dict(clean_environment(), **{POOL_ENV: str(self.base / "absent.toml")})
        done = subprocess.run([sys.executable, script, "status"], capture_output=True, text=True, env=bad)
        self.assertEqual(done.returncode, 2)
        self.assertIn("absent.toml", done.stderr)


class MeasurementTests(unittest.TestCase):
    VM_STAT = (
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
        "Pages free:                               1000.\n"
        "Pages active:                             5000.\n"
        "Pages inactive:                           2000.\n"
        "Pages speculative:                        500.\n"
    )

    def test_vm_stat_sums_free_inactive_and_speculative_pages(self) -> None:
        self.assertAlmostEqual(machine_pool.parse_vm_stat(self.VM_STAT), 3500 * 16384 / (1024 * 1024))

    def test_unparseable_vm_stat_fails(self) -> None:
        with self.assertRaisesRegex(machine_pool.PoolError, "page size"):
            machine_pool.parse_vm_stat("Pages free: 1.\n")
        with self.assertRaisesRegex(machine_pool.PoolError, "Pages speculative"):
            machine_pool.parse_vm_stat(self.VM_STAT.replace("Pages speculative:", "Pages other:"))

    def test_meminfo_reports_mem_available(self) -> None:
        self.assertAlmostEqual(machine_pool.parse_meminfo("MemTotal: 8000000 kB\nMemAvailable:    2048000 kB\n"), 2000.0)
        with self.assertRaisesRegex(machine_pool.PoolError, "MemAvailable"):
            machine_pool.parse_meminfo("MemTotal: 8000000 kB\n")

    def test_unsupported_platform_fails(self) -> None:
        with mock.patch.object(machine_pool.sys, "platform", "plan9"), \
                self.assertRaisesRegex(machine_pool.PoolError, "unsupported platform 'plan9'"):
            machine_pool.measure_available_memory_mb()

    def test_vm_stat_failure_fails(self) -> None:
        with mock.patch.object(machine_pool.sys, "platform", "darwin"), \
                mock.patch.object(machine_pool.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="boom", stdout="")), \
                self.assertRaisesRegex(machine_pool.PoolError, "vm_stat exited 1"):
            machine_pool.measure_available_memory_mb()

    def test_load_per_cpu_needs_a_cpu_count(self) -> None:
        with mock.patch.object(machine_pool.os, "cpu_count", return_value=None), \
                self.assertRaisesRegex(machine_pool.PoolError, "cpu_count"):
            machine_pool.measure_load_per_cpu()


class EnvironmentPropagationTests(unittest.TestCase):
    def test_check_environments_keep_the_pool_variables(self) -> None:
        source = {POOL_ENV: "/pool.toml", LEASE_ENV: '{"id": "x", "pooled": false}', CLASS_ENV: "finalize",
                  "GH_TOKEN": "secret"}
        with tempfile.TemporaryDirectory() as directory:
            for env in (platform_common.credential_free_env(dict(source), Path(directory)),
                        platform_common.project_check_env(dict(source), Path(directory) / "home", {}, Path(directory)),
                        workers.credential_free_env(dict(source), Path(directory)),
                        platform_common.validation_subprocess_env(source)):
                for name in POOL_VARIABLES:
                    self.assertEqual(env[name], source[name], name)
            self.assertNotIn("GH_TOKEN", platform_common.credential_free_env(dict(source), Path(directory)))


class IntegrationTests(PoolFixture):
    # Real child processes measure the host; admission must never depend on how busy the test machine is.
    MAX_LOAD_PER_CPU = 1_000_000.0
    MIN_AVAILABLE_MEMORY_MB = 1
    TOKENS = 3

    def patched_environment(self, **extra: str) -> mock._patch_dict:
        return mock.patch.dict(os.environ, {**clean_environment(), POOL_ENV: str(self.config_path), **extra}, clear=True)

    def test_select_checks_execute_acquires_once_and_commands_inherit_the_lease(self) -> None:
        marker = self.base / "inherited.json"
        code = (
            "import json, os, sys\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "import machine_pool\n"
            "payload = json.loads(os.environ['DEV_PLATFORM_MACHINE_POOL_LEASE'])\n"
            "[os.fstat(fd) for fd in payload['fds']]\n"
            "with machine_pool.lease(1, 'inner') as inner:\n"
            f"    open({str(marker)!r}, 'w').write(json.dumps({{'nested': inner.nested, 'weight': inner.weight, 'fds': len(payload['fds'])}}))\n"
        )
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"
        out = io.StringIO()
        with self.patched_environment(DEV_PLATFORM_TEST_JOBS="2"), mock.patch.object(machine_pool, "_git_branch", return_value="b"), \
                contextlib.redirect_stdout(out):
            result = select_checks.execute(ROOT, [{"id": "c", "commands": [command]}])
        self.assertEqual(result, 0, out.getvalue())
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8")), {"nested": True, "weight": 2, "fds": 2})
        self.assertEqual(out.getvalue().count("DEV_PLATFORM_MACHINE_POOL: acquired"), 1)
        self.assertEqual(machine_pool.read_holders(self.config), [])
        self.assertNotIn(LEASE_ENV, os.environ)

    def test_select_checks_execute_unpooled_prints_the_declared_line_once(self) -> None:
        out = io.StringIO()
        with mock.patch.dict(os.environ, clean_environment(), clear=True), contextlib.redirect_stdout(out):
            result = select_checks.execute(ROOT, [{"id": "c", "commands": ["true", "true"]}])
        self.assertEqual(result, 0)
        self.assertEqual(out.getvalue().count("DEV_PLATFORM_MACHINE_POOL: not configured"), 1)

    def test_select_checks_execute_fails_explicitly_on_a_misconfigured_pool(self) -> None:
        err = io.StringIO()
        with mock.patch.dict(os.environ, {**clean_environment(), POOL_ENV: str(self.base / "absent.toml")}, clear=True), \
                mock.patch.object(select_checks.subprocess, "run", side_effect=AssertionError("must not run")), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            result = select_checks.execute(ROOT, [{"id": "c", "commands": ["true"]}])
        self.assertEqual(result, 2)
        self.assertIn("absent.toml", err.getvalue())

    def run_groups(self, *argv: str) -> tuple[int, dict]:
        captured: dict = {}

        def fake_execute(root, start_dir, groups, jobs, verbose, pass_fds=()):
            captured.update(jobs=jobs, pass_fds=pass_fds, holders=machine_pool.read_holders(self.config))
            return []

        root = self.base / "project"
        (root / "tests").mkdir(parents=True)
        config = {"test_groups": {"g": {"targets": ["test_x"], "mode": "parallel"}}}
        with mock.patch.object(run_test_groups, "current_worktree_root", return_value=root), \
                mock.patch.object(run_test_groups, "load_check_config", return_value=config), \
                mock.patch.object(run_test_groups, "execute", side_effect=fake_execute), \
                mock.patch.object(sys, "argv", ["run_test_groups.py", *argv]), \
                contextlib.redirect_stdout(io.StringIO()):
            code = run_test_groups.main()
        return code, captured

    def test_run_test_groups_bounds_jobs_by_the_lease_weight_and_passes_the_descriptors(self) -> None:
        with self.patched_environment():
            code, captured = self.run_groups("--group", "g", "--jobs", "8")
        self.assertEqual(code, 0)
        self.assertEqual(captured["jobs"], 3)  # --jobs 8 bounded by the 3 configured tokens
        self.assertEqual(len(captured["pass_fds"]), 3)
        self.assertEqual(sum(len(h["slots"]) for h in captured["holders"]), 3)
        self.assertEqual(machine_pool.read_holders(self.config), [])

    def test_run_test_groups_inside_a_lease_acquires_nothing_and_respects_its_weight(self) -> None:
        environ = {POOL_ENV: str(self.config_path)}
        with machine_pool.lease(2, "parent", environ=environ, hooks=fast_hooks()) as parent, \
                self.patched_environment(**{LEASE_ENV: environ[LEASE_ENV]}):
            code, captured = self.run_groups("--group", "g", "--jobs", "8")
        self.assertEqual(code, 0)
        self.assertEqual(captured["jobs"], 2)
        self.assertEqual(captured["pass_fds"], parent.fds)
        self.assertEqual(sum(len(h["slots"]) for h in captured["holders"]), 2)  # the parent's, nothing extra

    def test_run_test_groups_list_and_coverage_do_not_acquire(self) -> None:
        with self.patched_environment(), mock.patch.object(machine_pool, "lease", side_effect=AssertionError("must not lease")), \
                mock.patch.object(run_test_groups, "current_worktree_root", return_value=self.base), \
                mock.patch.object(run_test_groups, "load_check_config",
                                  return_value={"test_groups": {"g": {"targets": ["test_x"], "mode": "parallel"}}}), \
                mock.patch.object(run_test_groups, "coverage_report", return_value={}), \
                mock.patch.object(run_test_groups, "require_total_coverage"), \
                mock.patch.object(sys, "argv", ["run_test_groups.py", "--list"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_test_groups.main(), 0)
            with mock.patch.object(sys, "argv", ["run_test_groups.py", "--verify-coverage"]):
                self.assertEqual(run_test_groups.main(), 0)

    def test_requirement_integration_leases_once_with_the_finalize_class(self) -> None:
        seen = []

        real_run = subprocess.run

        def run(command, **kwargs):
            if isinstance(command, list):  # the pool's own vm_stat measurement
                return real_run(command, **kwargs)
            seen.append((command, kwargs["env"].get(LEASE_ENV), kwargs["pass_fds"], machine_pool.read_holders(self.config)))
            return SimpleNamespace(returncode=0)

        root = self.base / "project"
        root.mkdir()
        with self.patched_environment(), \
                mock.patch.object(integration, "_full_check_commands", return_value=["first", "second"]), \
                mock.patch.object(integration, "_check_environment", side_effect=lambda r, s: dict(os.environ)), \
                mock.patch.object(integration.subprocess, "run", side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            integration._run_full_checks(root)
        self.assertEqual([entry[0] for entry in seen], ["first", "second"])
        for _, exported, fds, holders in seen:
            self.assertEqual(json.loads(exported)["pooled"], True)
            self.assertEqual(len(fds), len(json.loads(exported)["fds"]))
            self.assertEqual([h["class"] for h in holders], ["finalize"])
        self.assertEqual({entry[1] for entry in seen}.__len__(), 1)  # the same lease for the whole loop
        self.assertEqual(machine_pool.read_holders(self.config), [])

    def test_requirement_integration_reports_a_pool_failure_without_running(self) -> None:
        with mock.patch.dict(os.environ, {**clean_environment(), POOL_ENV: str(self.base / "absent.toml")}, clear=True), \
                mock.patch.object(integration, "_full_check_commands", return_value=["first"]), \
                mock.patch.object(integration.subprocess, "run", side_effect=AssertionError("must not run")), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(integration.RequirementIntegrationError, "machine pool.*absent.toml"):
                integration._run_full_checks(self.base)

    def test_finalization_checks_runner_declares_the_finalize_class_and_keeps_the_pool_variables(self) -> None:
        done = subprocess.CompletedProcess("checks", 0, stdout="", stderr="")
        with mock.patch.object(final.subprocess, "run", return_value=done) as run:
            final.trusted_checks_runner(Path("/checkout"), {POOL_ENV: "/pool.toml", "KEEP": "1"})
        env = run.call_args.kwargs["env"]
        self.assertEqual((env[CLASS_ENV], env[POOL_ENV], env["KEEP"]), ("finalize", "/pool.toml", "1"))


if __name__ == "__main__":
    unittest.main()
