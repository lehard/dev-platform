"""The one credential mechanism of lifecycle workers.

GitHub access is the active ``gh`` credential. The Claude credential has exactly one source per placement:
an enabled ``[operator]`` selects ``[independent_review.login.claude] token_file``, anything else (a hosted
runner) the ``CLAUDE_CODE_OAUTH_TOKEN`` of the job's environment. Placement selects the source; which value
happens to be present never does. A missing or invalid source raises, naming the setting and never the value.
"""
from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path
from typing import Any

TOKEN_SETTING = "[independent_review.login.claude] token_file"
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
CLAUDE_PROVIDER = "claude"


class CredentialError(RuntimeError):
    pass


def operator_placement(config: Mapping[str, Any]) -> bool:
    """Whether this checkout is an operator node (``[operator] enabled = true``)."""
    operator = config.get("operator")
    return isinstance(operator, dict) and operator.get("enabled") is True


def remove_ambient_token(config: Mapping[str, Any], environ: MutableMapping[str, str]) -> None:
    """Drop an exported token on the operator node: it is neither a source there nor for its children."""
    if operator_placement(config):
        environ.pop(TOKEN_ENV, None)


def claude_token_file(config: Mapping[str, Any]) -> Path:
    try:
        token_file = config["independent_review"]["login"]["claude"]["token_file"]
    except (KeyError, TypeError):
        raise CredentialError(f"operator setting {TOKEN_SETTING} is missing") from None
    if not isinstance(token_file, str) or not token_file.strip():
        raise CredentialError(f"operator setting {TOKEN_SETTING} must be a non-empty path")
    return Path(os.path.expanduser(token_file))


def read_claude_token(config: Mapping[str, Any]) -> str:
    path = claude_token_file(config)
    try:
        info = path.stat()
    except OSError as error:
        raise CredentialError(f"token file {path} named by {TOKEN_SETTING} is not readable: {error.strerror}") from None
    if not stat.S_ISREG(info.st_mode):
        raise CredentialError(f"token file {path} is not a regular file")
    if info.st_mode & 0o077:
        raise CredentialError(f"token file {path} is accessible by group or others; its mode must be 0600")
    value = path.read_text().strip()
    if not value:
        raise CredentialError(f"token file {path} is empty")
    return value


def resolve_claude_token(config: Mapping[str, Any], environ: Mapping[str, str]) -> str:
    """The Claude credential of this placement."""
    if operator_placement(config):
        return read_claude_token(config)
    value = environ.get(TOKEN_ENV, "").strip()
    if not value:
        raise CredentialError(f"{TOKEN_ENV} is empty; a worker without an enabled [operator] takes it only from "
                              "the job's environment")
    return value


def llm_env(config: Mapping[str, Any], providers: Iterable[str], environ: Mapping[str, str]) -> dict[str, str]:
    """What an LLM process of these providers adds to its credential-free environment."""
    if CLAUDE_PROVIDER not in providers:
        return {}
    return {TOKEN_ENV: resolve_claude_token(config, environ)}


def active_gh_token(checkout: Path, env: Mapping[str, str]) -> str:
    """gh's active token (an exported GH_TOKEN, else the gh login). gh output is never echoed."""
    done = subprocess.run(["gh", "auth", "token"], cwd=checkout, env={**env, "GH_PROMPT_DISABLED": "1"},
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    token = done.stdout.strip() if done.returncode == 0 else ""
    if not token:
        raise CredentialError("harness GitHub push requires an authenticated gh credential (gh auth token failed)")
    return token
