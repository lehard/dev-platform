"""The Claude token file of the sandboxed writer: ``[independent_review.login.claude] token_file``.

A missing or invalid source raises, naming the setting and never the value.
"""
from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

TOKEN_SETTING = "[independent_review.login.claude] token_file"
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"


class CredentialError(RuntimeError):
    pass


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
