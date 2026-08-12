#!/usr/bin/env python3
"""Containment observation and legacy fallback for write-capable delegation.

See openspec/specs/platform-delegation/spec.md and the active
wire-runtime-delegation-containment change for the contract. A delegation is
platform-contained when it has a valid assigned worktree, a proven native or
fallback boundary, and the post-delegation comparison below. Native runtime
containment is the preferred prevention layer; this module observes it and
retains the smallest compatibility fallback. ``run_guarded_delegation`` is a
backwards-compatible name, while new native callers should use
``run_observed_delegation`` to avoid implying that a second custom guard is
what protects the filesystem.

Guarded flow, always in this order:

    validate assigned_worktree -> determine enforcement tier -> pre-snapshot ->
    launch child with cwd=assigned_worktree -> post-snapshot (always) ->
    classify -> record friction on violation -> return/raise

Enforcement tiers are honest, not aspirational:

- HARD means a proven pre-write boundary exists before the child can mutate
  protected repository paths outside `assigned_worktree`: for Codex, a real
  OS writable-root sandbox (Landlock/Seatbelt, exposed via
  `codex --sandbox workspace-write`) whose known additional temporary writable
  roots do not overlap the integration or assigned-worktree topology;
  for Claude, a platform-installed PreToolUse hook denying Write/Edit/
  NotebookEdit targets outside `assigned_worktree`, valid only when no
  shell-capable tool is also enabled for the same delegated session.
- DETECTION_ONLY means the only enforcement is this module's own post-hoc
  comparison. Detection-only delegation refuses to start while the
  integration checkout already has uncommitted state, since it cannot tell
  apart pre-existing dirt from writer-caused damage the way a hard-contained
  run's post-check still can.

This module never stashes/resets/cleans/deletes anything in the integration
copy. It does not vendor OpenSpec-generated Claude/Codex skills, and any
runtime settings it writes for a guarded Claude child are ephemeral temp-
directory files, never a project-tracked path.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from delegation_containment import (
    ContainmentError,
    ContainmentResult,
    check_containment,
    format_violation_message,
    record_containment_friction,
    resolve_assigned_worktree,
    snapshot,
)


class EnforcementTier(str, Enum):
    HARD = "hard"
    DETECTION_ONLY = "detection-only"


@dataclass(frozen=True)
class EnforcementDecision:
    tier: EnforcementTier
    mechanism: str
    detail: str


@dataclass(frozen=True)
class GuardedRunResult:
    launched: bool
    returncode: int | None
    tier: EnforcementTier
    mechanism: str
    containment: ContainmentResult
    violation: bool
    message: str | None


class GuardedChildError(ContainmentError):
    """The delegated child did not complete normally (exec failure, timeout, cancellation).

    The post-delegation containment check still ran before this was raised; `result`
    carries its outcome so callers do not lose containment information just because
    the child itself failed.
    """

    def __init__(self, message: str, result: GuardedRunResult) -> None:
        super().__init__(message)
        self.result = result


# --------------------------------------------------------------------------
# Core guarded entrypoint -- runtime-agnostic.
# --------------------------------------------------------------------------


def run_observed_delegation(
    *,
    integration_root: Path,
    assigned_worktree: str | Path,
    argv: list[str],
    tier_decision: EnforcementDecision,
    env: dict[str, str] | None = None,
    task: str | None = None,
    timeout: float | None = None,
    stdout_line_hook: Callable[[str], None] | None = None,
) -> GuardedRunResult:
    """Run one delegated child under a native/fallback containment contract.

    Always validates assigned_worktree first (fail closed before any launch), always
    snapshots before launch, always launches with cwd=assigned_worktree, and always
    snapshots again -- even if the child raises, times out, or is cancelled -- before
    returning or raising. Never mutates integration_root itself.

    ``stdout_line_hook``, when given, receives each stdout/stderr line as the
    child produces it (merged, so live output ordering is preserved) instead
    of letting the child inherit the parent's stdout directly. Callers use
    this to both forward output for live visibility and opportunistically
    parse structured runtime events (for example Codex's ``--json`` event
    stream) without adding a second execution path. Note: with this hook set,
    ``timeout`` is only enforced after the child closes stdout (i.e. once it
    exits), not while blocked reading a line -- unused by any current caller.
    """
    resolved_worktree = resolve_assigned_worktree(integration_root, assigned_worktree)

    if tier_decision.tier is EnforcementTier.DETECTION_ONLY:
        dirty_precheck = snapshot(integration_root)
        if dirty_precheck.paths:
            dirty_paths = ", ".join(sorted(dirty_precheck.paths))
            raise ContainmentError(
                f"detection-only delegation ({tier_decision.mechanism}) refused to start: "
                f"integration checkout already has uncommitted state ({dirty_paths}). "
                "A detection-only writer cannot prove it did not touch pre-existing dirty "
                "state, so it must not launch until integration is clean."
            )
        before = dirty_precheck
    else:
        before = snapshot(integration_root)

    child_launched = False
    launch_exception: Exception | None = None
    completed: subprocess.CompletedProcess[str] | None = None
    process: subprocess.Popen[str] | None = None
    try:
        if stdout_line_hook is not None:
            process = subprocess.Popen(
                argv, cwd=resolved_worktree, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
            )
            child_launched = True
            assert process.stdout is not None
            for line in process.stdout:
                stdout_line_hook(line.rstrip("\n"))
            process.stdout.close()
            returncode = process.wait(timeout=timeout)
            completed = subprocess.CompletedProcess(argv, returncode)
        else:
            process = subprocess.Popen(argv, cwd=resolved_worktree, env=env, text=True)
            child_launched = True
            returncode = process.wait(timeout=timeout)
            completed = subprocess.CompletedProcess(argv, returncode)
    except subprocess.TimeoutExpired as exc:
        # The child was cancelled: it did start, so child_launched stays True.
        process.kill()
        process.wait()
        launch_exception = exc
    except Exception as exc:  # exec/spawn failure -- child never actually started
        launch_exception = exc
    finally:
        after = snapshot(integration_root)
        containment = check_containment(before, after)

    violation = containment.violated
    message = format_violation_message(resolved_worktree, containment) if violation else None
    if violation:
        record_containment_friction(
            integration_root, resolved_worktree, containment, task=task, enforcement_tier=tier_decision.tier.value
        )

    result = GuardedRunResult(
        launched=child_launched,
        returncode=completed.returncode if completed is not None else None,
        tier=tier_decision.tier,
        mechanism=tier_decision.mechanism,
        containment=containment,
        violation=violation,
        message=message,
    )

    if launch_exception is not None:
        raise GuardedChildError(
            f"delegated child did not complete normally ({launch_exception!r}); "
            f"containment {'VIOLATION' if violation else 'clean'} recorded before this error was raised.",
            result,
        ) from launch_exception

    return result


def run_guarded_delegation(
    *,
    integration_root: Path,
    assigned_worktree: str | Path,
    argv: list[str],
    tier_decision: EnforcementDecision,
    env: dict[str, str] | None = None,
    task: str | None = None,
    timeout: float | None = None,
) -> GuardedRunResult:
    """Compatibility alias for callers that still use the former guard name."""
    return run_observed_delegation(
        integration_root=integration_root,
        assigned_worktree=assigned_worktree,
        argv=argv,
        tier_decision=tier_decision,
        env=env,
        task=task,
        timeout=timeout,
    )


# --------------------------------------------------------------------------
# Codex adapter: real OS writable-root sandbox when the installed runtime supports it.
# --------------------------------------------------------------------------

CODEX_SANDBOX_FLAG = "--sandbox"
CODEX_SANDBOX_MODE = "workspace-write"
CODEX_CD_FLAG = "--cd"
_HARD_SANDBOX_OS = ("Darwin", "Linux")


def _codex_help_text(binary: str) -> str:
    try:
        # A real `codex exec --help` answers in milliseconds; this timeout only
        # guards against a genuinely hung process. It must stay generous enough
        # to survive legitimate CPU contention from concurrent mandatory test
        # groups (see dev-platform/checks.toml [test_groups]) -- a tighter bound
        # previously caused this to time out under contention and downgrade to
        # "sandbox-flag-unsupported" instead of reporting the real mechanism.
        completed = subprocess.run(
            [binary, "exec", "--help"], text=True, capture_output=True, check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout + completed.stderr


def _normalized_path(path: str | Path) -> Path:
    """Normalize filesystem paths with the same realpath semantics as the guard."""
    return Path(path).expanduser().resolve()


def _codex_runtime_temp_roots() -> tuple[Path, ...]:
    """Return only the extra Codex workspace-write roots established by evidence.

    Codex workspace-write can also allow system temporary roots. `/tmp` is the
    observed portable root and `$TMPDIR` is included explicitly because Python's
    tempfile resolver can be cached before an environment override is applied.
    The current tempfile root covers the platform-selected temporary location.
    """
    candidates: list[str | Path] = ["/tmp"]
    if configured := os.environ.get("TMPDIR"):
        candidates.append(configured)
    try:
        candidates.append(tempfile.gettempdir())
    except (OSError, RuntimeError):
        # An unreadable temp configuration means we retain the proven `/tmp`
        # root; callers still fail closed if a required path cannot be resolved.
        pass

    roots: list[Path] = []
    for candidate in candidates:
        try:
            resolved = _normalized_path(candidate)
        except OSError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _codex_temp_root_overlap(
    integration_root: str | Path,
    assigned_worktree: str | Path,
    runtime_temp_roots: tuple[str | Path, ...] | None,
) -> tuple[str, Path, Path] | None:
    """Return the first protected repository path overlapping an extra root."""
    roots = runtime_temp_roots if runtime_temp_roots is not None else _codex_runtime_temp_roots()
    normalized_roots = tuple(_normalized_path(root) for root in roots)
    protected_paths = (
        ("integration_root", _normalized_path(integration_root)),
        ("assigned_worktree", _normalized_path(assigned_worktree)),
    )
    for label, protected_path in protected_paths:
        for root in normalized_roots:
            if _path_is_within(protected_path, root):
                return label, protected_path, root
    return None


def determine_codex_tier(
    *,
    codex_bin: str | None = None,
    require_hard: bool = False,
    platform_system: str | None = None,
    integration_root: str | Path | None = None,
    assigned_worktree: str | Path | None = None,
    runtime_temp_roots: tuple[str | Path, ...] | None = None,
) -> EnforcementDecision:
    """Decide the enforcement tier for a platform-controlled Codex delegation.

    Empirically checks the installed codex binary's own --help output for the
    workspace-write sandbox flag rather than assuming a fixed CLI surface, since
    the interface can evolve. HARD additionally requires a normalized repository
    topology that does not overlap known runtime-added temporary writable roots.
    If require_hard is set and hard containment cannot be established, this
    fails closed (raises) instead of silently downgrading.
    """
    binary = shutil.which(codex_bin) if codex_bin else shutil.which("codex")
    system = platform_system or platform.system()

    if binary is None:
        decision = EnforcementDecision(
            EnforcementTier.DETECTION_ONLY,
            "detection-only:codex-binary-not-found",
            "codex executable not found on PATH; cannot establish a workspace-write sandbox.",
        )
    elif system not in _HARD_SANDBOX_OS:
        decision = EnforcementDecision(
            EnforcementTier.DETECTION_ONLY,
            f"detection-only:unsupported-os:{system}",
            f"No supported OS sandbox (Seatbelt/Landlock) is known for platform {system!r}.",
        )
    else:
        help_text = _codex_help_text(binary)
        if CODEX_SANDBOX_FLAG not in help_text or CODEX_SANDBOX_MODE not in help_text:
            decision = EnforcementDecision(
                EnforcementTier.DETECTION_ONLY,
                "detection-only:sandbox-flag-unsupported",
                "Installed codex build does not advertise a workspace-write sandbox flag in `codex exec --help`.",
            )
        elif integration_root is None or assigned_worktree is None:
            decision = EnforcementDecision(
                EnforcementTier.DETECTION_ONLY,
                "detection-only:topology-unavailable",
                "Codex repository topology was not supplied, so temp-root overlap cannot be ruled out.",
            )
        else:
            try:
                overlap = _codex_temp_root_overlap(integration_root, assigned_worktree, runtime_temp_roots)
            except OSError as exc:
                decision = EnforcementDecision(
                    EnforcementTier.DETECTION_ONLY,
                    "detection-only:topology-unresolvable",
                    f"Codex repository topology could not be normalized: {exc}",
                )
            else:
                if overlap is not None:
                    label, protected_path, temp_root = overlap
                    decision = EnforcementDecision(
                        EnforcementTier.DETECTION_ONLY,
                        "detection-only:runtime-temp-root-overlap",
                        f"{label} {protected_path} resolves inside Codex runtime-writable temp root {temp_root}.",
                    )
                else:
                    decision = EnforcementDecision(
                        EnforcementTier.HARD,
                        "codex-workspace-write-sandbox",
                        f"codex {CODEX_SANDBOX_FLAG} {CODEX_SANDBOX_MODE} on {system}; "
                        "protected repository paths are outside known runtime-added temp roots.",
                    )

    if require_hard and decision.tier is not EnforcementTier.HARD:
        raise ContainmentError(
            f"hard containment was required for this Codex delegation but could not be established: {decision.detail}"
        )
    return decision


def build_codex_argv(
    codex_bin: str,
    assigned_worktree: Path,
    tier: EnforcementTier,
    prompt_args: list[str],
) -> list[str]:
    """Build the codex CLI argv for the resolved tier.

    Hard tier supplies only the assigned worktree through Codex flags and
    deliberately omits --add-dir for any other repository path. Runtime-known
    temporary roots are assessed separately by determine_codex_tier.
    """
    argv = [codex_bin, "exec"]
    if tier is EnforcementTier.HARD:
        argv += [CODEX_SANDBOX_FLAG, CODEX_SANDBOX_MODE, CODEX_CD_FLAG, str(assigned_worktree)]
    argv += prompt_args
    return argv


# --------------------------------------------------------------------------
# Claude adapter: hook-assisted prevention for structured write tools, truthful
# about the shell boundary.
# --------------------------------------------------------------------------

_GUARD_SCRIPT_TEMPLATE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    # Ephemeral PreToolUse guard generated by delegated_write_guard.py. Not a
    # tracked project file -- regenerated fresh for each guarded delegation.
    import json
    import sys
    from pathlib import Path

    ASSIGNED_WORKTREE = Path({assigned_worktree!r}).resolve()
    TARGET_KEYS = ("file_path", "path", "notebook_path")


    def _decision(permission_decision, reason=None):
        payload = {{
            "hookSpecificOutput": {{
                "hookEventName": "PreToolUse",
                "permissionDecision": permission_decision,
            }}
        }}
        if reason is not None:
            payload["hookSpecificOutput"]["permissionDecisionReason"] = reason
        json.dump(payload, sys.stdout)


    def main() -> int:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            _decision("allow")
            return 0
        tool_input = payload.get("tool_input") or {{}}
        target = next((tool_input[key] for key in TARGET_KEYS if key in tool_input), None)
        if target is None:
            _decision("allow")
            return 0
        resolved = Path(target)
        if not resolved.is_absolute():
            resolved = ASSIGNED_WORKTREE / resolved
        resolved = resolved.resolve()
        try:
            resolved.relative_to(ASSIGNED_WORKTREE)
        except ValueError:
            _decision("deny", f"{{resolved}} is outside the assigned worktree {{ASSIGNED_WORKTREE}}")
            return 0
        _decision("allow")
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """
)


def render_pretooluse_guard_script(assigned_worktree: Path) -> str:
    return _GUARD_SCRIPT_TEMPLATE.format(assigned_worktree=str(assigned_worktree))


@dataclass(frozen=True)
class ClaudeGuard:
    guard_dir: Path
    hook_script: Path
    settings_path: Path


def write_claude_guard(assigned_worktree: Path, *, guard_dir: Path | None = None) -> ClaudeGuard:
    """Write an ephemeral PreToolUse hook + settings.json denying writes outside assigned_worktree.

    Always written under a fresh temp directory unless the caller explicitly provides
    guard_dir; never touches a project-tracked settings path.
    """
    directory = guard_dir or Path(tempfile.mkdtemp(prefix="dev-platform-guard-"))
    directory.mkdir(parents=True, exist_ok=True)
    hook_script = directory / "pretooluse_guard.py"
    hook_script.write_text(render_pretooluse_guard_script(assigned_worktree), encoding="utf-8")
    hook_script.chmod(hook_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{sys.executable} {hook_script}",
                        }
                    ],
                }
            ]
        }
    }
    settings_path = directory / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return ClaudeGuard(guard_dir=directory, hook_script=hook_script, settings_path=settings_path)


def determine_claude_tier(*, shell_enabled: bool) -> EnforcementDecision:
    """Decide the enforcement tier for a platform-controlled Claude Code delegation.

    Structured Write/Edit/NotebookEdit targets can be resolved and denied before the
    write occurs by a PreToolUse hook -- a real pre-write enforcement point -- so a
    session restricted to those tools is HARD. Arbitrary shell access defeats that
    boundary (a shell command can write via `cat`, `sed -i`, `mv`, ...), so any
    shell-capable session is DETECTION_ONLY regardless of the hook being installed.
    """
    if shell_enabled:
        return EnforcementDecision(
            EnforcementTier.DETECTION_ONLY,
            "detection-only:claude-shell-capable",
            "Arbitrary shell-capable Claude delegation has no proven OS filesystem sandbox; "
            "command-text inspection alone is not hard containment.",
        )
    return EnforcementDecision(
        EnforcementTier.HARD,
        "claude-structured-write-hook",
        "Write/Edit/NotebookEdit targets are resolved and denied before the write via a "
        "platform-installed PreToolUse hook; no shell-capable tool is enabled for this session.",
    )


def build_claude_argv(claude_bin: str, guard: ClaudeGuard, extra_args: list[str]) -> list[str]:
    return [claude_bin, "--settings", str(guard.settings_path), *extra_args]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _split_argv(raw: list[str]) -> list[str]:
    if raw and raw[0] == "--":
        return raw[1:]
    return raw


def _cmd_codex(args: argparse.Namespace) -> int:
    integration_root = Path(args.integration_root).resolve()
    resolved_worktree = resolve_assigned_worktree(integration_root, args.assigned_worktree)
    try:
        tier_decision = determine_codex_tier(
            codex_bin=args.codex_bin,
            require_hard=args.require_hard,
            integration_root=integration_root,
            assigned_worktree=resolved_worktree,
        )
    except ContainmentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    binary = args.codex_bin or shutil.which("codex") or "codex"
    argv = build_codex_argv(binary, resolved_worktree, tier_decision.tier, _split_argv(args.child_argv))
    return _run_and_report(integration_root, args.assigned_worktree, argv, tier_decision, args.task)


def _cmd_claude(args: argparse.Namespace) -> int:
    integration_root = Path(args.integration_root).resolve()
    resolved_worktree = resolve_assigned_worktree(integration_root, args.assigned_worktree)
    tier_decision = determine_claude_tier(shell_enabled=args.shell_enabled)
    guard = write_claude_guard(resolved_worktree)
    binary = args.claude_bin or shutil.which("claude") or "claude"
    argv = build_claude_argv(binary, guard, _split_argv(args.child_argv))
    return _run_and_report(integration_root, args.assigned_worktree, argv, tier_decision, args.task)


def _run_and_report(
    integration_root: Path,
    assigned_worktree: str,
    argv: list[str],
    tier_decision: EnforcementDecision,
    task: str | None,
) -> int:
    print(f"enforcement tier: {tier_decision.tier.value} ({tier_decision.mechanism})", file=sys.stderr)
    try:
        result = run_guarded_delegation(
            integration_root=integration_root,
            assigned_worktree=assigned_worktree,
            argv=argv,
            tier_decision=tier_decision,
            task=task,
        )
    except GuardedChildError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ContainmentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if result.violation:
        print(result.message, file=sys.stderr)
        return 1
    return result.returncode or 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded entrypoint for write-capable delegated execution.")
    sub = parser.add_subparsers(dest="runtime", required=True)

    codex = sub.add_parser("codex", help="Delegate to platform-controlled Codex with a hard writable-root sandbox.")
    codex.add_argument("--integration-root", required=True)
    codex.add_argument("--assigned-worktree", required=True)
    codex.add_argument("--task")
    codex.add_argument("--codex-bin")
    codex.add_argument("--require-hard", action="store_true")
    codex.add_argument("child_argv", nargs=argparse.REMAINDER)
    codex.set_defaults(func=_cmd_codex)

    claude = sub.add_parser("claude", help="Delegate to platform-controlled Claude Code with a structured-write hook guard.")
    claude.add_argument("--integration-root", required=True)
    claude.add_argument("--assigned-worktree", required=True)
    claude.add_argument("--task")
    claude.add_argument("--claude-bin")
    claude.add_argument("--shell-enabled", action="store_true", help="Session includes a shell-capable tool (Bash or equivalent); forces detection-only.")
    claude.add_argument("child_argv", nargs=argparse.REMAINDER)
    claude.set_defaults(func=_cmd_claude)

    return parser


if __name__ == "__main__":
    parsed = build_parser().parse_args()
    raise SystemExit(parsed.func(parsed))
