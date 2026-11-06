"""The environment conditions of lifecycle worker jobs, proven before the first claim.

``work-next --run`` and the standalone ``worker-preflight`` command evaluate the same conditions through
:func:`lifecycle_preflight.run_preflight`: every result is printed (on stderr, stdout carries the worker's JSON)
and one refusal names all unmet conditions. Each condition calls the function the real path calls. A condition
id is also the only value a :class:`lifecycle_workers.EnvironmentFailure` may carry, so a persistent environment
defect stops here, before any claim, and the free-of-charge environment class cannot loop.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from lifecycle_preflight import (NOT_APPLICABLE, PASSED, Condition, ConditionResult, PreflightContext, PreflightRefusal,
                                 check_shared_workspace, run_preflight)

ENTRY = "work-next --run"
POST_MERGE = frozenset({"retrospective", "terminal-reconciliation", "cleanup"})
PROVIDER_KINDS = frozenset({"review", "repair", "integration-repair"})
WRITE_KINDS = frozenset({"repair", "integration-repair"})


@dataclass(frozen=True)
class WorkerContext:
    root: Path
    repo: str
    kinds: frozenset[str]
    providers: tuple[str, ...] = ()
    writer: bool = False
    entry: str = ENTRY


def _config(ctx: WorkerContext) -> dict:
    from _platform_common import read_platform_config

    return read_platform_config(ctx.root)


def check_trusted_contract(ctx: WorkerContext) -> ConditionResult:
    try:
        _config(ctx)
    except RuntimeError as exc:
        raise PreflightRefusal(str(exc)) from exc
    return ConditionResult(PASSED, f"the contract of {ctx.root} passes the schema")


def check_github_credential(ctx: WorkerContext) -> ConditionResult:
    import lifecycle_workers as workers
    import worker_credentials

    try:
        workers.active_gh_token(ctx.root, dict(os.environ))
    except workers.WorkerError as exc:
        raise PreflightRefusal(str(exc)) from exc
    if not worker_credentials.operator_placement(_config(ctx)):
        return ConditionResult(PASSED, "gh credential active; a hosted token's scope is proven by hosted-preflight")
    permissions = workers._gh_json("api", f"repos/{ctx.repo}").get("permissions") or {}
    if permissions.get("push") is not True:
        raise PreflightRefusal(f"the active gh credential has no write access to {ctx.repo}")
    return ConditionResult(PASSED, f"gh credential active with write access to {ctx.repo}")


def check_provider_credential(ctx: WorkerContext) -> ConditionResult:
    import worker_credentials

    if not ctx.kinds & PROVIDER_KINDS:
        return ConditionResult(NOT_APPLICABLE, "no requested kind starts a provider")
    if not ctx.providers:
        return ConditionResult(NOT_APPLICABLE, "the selected job names its provider; it is proven before claim")
    config = _config(ctx)
    problems = []
    for provider in ctx.providers:
        try:
            worker_credentials.llm_env(config, [provider], os.environ)
        except worker_credentials.CredentialError as exc:
            problems.append(f"{provider}: {exc}")
    if len(problems) == len(ctx.providers):
        raise PreflightRefusal("; ".join(problems))
    return ConditionResult(PASSED, f"credential available for {len(ctx.providers) - len(problems)} provider(s)")


def check_writer_runtime(ctx: WorkerContext) -> ConditionResult:
    import sandboxed_writer

    if not ctx.writer:
        return ConditionResult(NOT_APPLICABLE, "no sandboxed writer requested")
    try:
        sandboxed_writer.require_macos()
        sandboxed_writer.srt_launcher()
        sandboxed_writer.require_writer_cli()
    except sandboxed_writer.SandboxedWriterError as exc:
        raise PreflightRefusal(str(exc)) from exc
    return ConditionResult(PASSED, "macOS, the sandbox runtime launcher and the Claude CLI are available")


def check_finalize_tools(ctx: WorkerContext) -> ConditionResult:
    if "finalize" not in ctx.kinds:
        return ConditionResult(NOT_APPLICABLE, "finalize not requested")
    if shutil.which("openspec") is None:
        raise PreflightRefusal("the OpenSpec CLI is not on PATH")
    return ConditionResult(PASSED, "the OpenSpec CLI is available")


def check_process_tool(ctx: WorkerContext) -> ConditionResult:
    if "cleanup" not in ctx.kinds:
        return ConditionResult(NOT_APPLICABLE, "cleanup not requested")
    if shutil.which("lsof") is None:
        raise PreflightRefusal("the active-process check needs lsof on PATH")
    return ConditionResult(PASSED, "lsof is available")


def check_backlog_access(ctx: WorkerContext) -> ConditionResult:
    import lifecycle_workers as workers

    if not ctx.kinds & POST_MERGE:
        return ConditionResult(NOT_APPLICABLE, "no post-merge kind requested")
    backlog = _config(ctx).get("development_backlog", {}).get("repository")
    if not backlog:
        raise PreflightRefusal("[development_backlog] repository is not configured")
    try:
        workers._gh_json("api", f"repos/{backlog}")
    except workers.WorkerError as exc:
        raise PreflightRefusal(f"the Development Backlog is not readable: {exc}") from exc
    return ConditionResult(PASSED, "the Development Backlog is readable")


def check_post_merge_workspace(ctx: WorkerContext) -> ConditionResult:
    if not ctx.kinds & POST_MERGE:
        return ConditionResult(NOT_APPLICABLE, "no post-merge kind requested")
    return check_shared_workspace(PreflightContext(ctx.root, ctx.root, "", ctx.entry))


CONDITIONS: tuple[Condition, ...] = (
    Condition("trusted-contract", (), check_trusted_contract),
    Condition("github-credential", (), check_github_credential),
    Condition("provider-credential", (), check_provider_credential),
    Condition("writer-runtime", (), check_writer_runtime),
    Condition("finalize-tools", (), check_finalize_tools),
    Condition("process-tool", (), check_process_tool),
    Condition("backlog-access", (), check_backlog_access),
    Condition("shared-workspace", (), check_post_merge_workspace),
)
CONDITION_IDS = tuple(condition.id for condition in CONDITIONS)


def run(ctx: WorkerContext) -> None:
    """Print every condition and raise ``PreflightRefused`` naming all unmet ones."""
    import lifecycle_workers as workers

    try:
        with contextlib.redirect_stdout(sys.stderr):
            run_preflight(ctx, conditions=CONDITIONS)
    except SystemExit as exc:
        raise workers.PreflightRefused(str(exc.code)) from exc
