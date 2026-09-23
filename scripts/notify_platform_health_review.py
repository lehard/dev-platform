#!/usr/bin/env python3
"""Send an optional, short external notification for a published Platform
Health Review report.

This is the deterministic, non-agentic notification step for the
`platform-health-review` capability (openspec/specs/platform-health-review/spec.md).
It runs after the combined report Issue has already been published by
`scripts/publish_platform_health_review_report.py` (a separate, prior
workflow job) and never re-evaluates or duplicates that report.

Boundary and secret handling:

- GitHub (the report Issue itself) is always the base channel and needs no
  configuration here.
- Telegram (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`) and a generic outbound
  webhook (`NOTIFY_WEBHOOK_URL`) are optional adapters. Each is read only
  from this process's own environment (GitHub Actions repository secrets in
  production); this script never reads them from any repository file.
- A channel whose required secret(s) are absent is silently skipped -- that
  is not an error, since GitHub remains fully sufficient on its own.
- A failure delivering to one channel never prevents attempting the other.
- The payload is always a short summary plus the report Issue link, never
  the full report body.
- No secret value (bot token, chat id, or webhook URL) is ever written to
  stdout/stderr, including inside error text: failures are reported by
  exception type / safe HTTP status only, never by echoing the underlying
  exception message, which could otherwise embed a URL containing a secret.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


class NotificationError(RuntimeError):
    """Raised when a single channel's delivery fails.

    The message text is always safe to print: see `_safe_error_detail`.
    """


@dataclass(frozen=True)
class Notification:
    summary: str
    issue_url: str
    issue_number: str | None = None

    def text(self) -> str:
        header = (self.summary or "").strip()
        link = (self.issue_url or "").strip()
        if header and link:
            return f"{header}\n{link}"
        return header or link


class HttpSender:
    """Thin, injectable HTTP POST wrapper.

    Kept small so tests can supply a fake instead of making a real network
    call, mirroring the `GhClient` pattern in
    `publish_platform_health_review_report.py`.
    """

    def post_json(self, url: str, payload: dict, *, timeout: float = 10.0) -> None:
        data = json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status = getattr(response, "status", 200)
            if status >= 400:
                raise NotificationError(f"HTTP {status}")


def _safe_error_detail(exc: Exception) -> str:
    """Return a short, secret-free description of a delivery failure.

    Deliberately never returns `str(exc)`: some HTTP client error messages
    embed the request URL, which for Telegram includes the bot token. Only
    the exception type (and, for an HTTP error, its numeric status code) is
    ever surfaced.
    """
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    return type(exc).__name__


@dataclass(frozen=True)
class ChannelResult:
    name: str
    attempted: bool
    ok: bool
    error: str | None = None


def send_telegram(notification: Notification, *, bot_token: str, chat_id: str, sender: HttpSender) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": notification.text(),
        "disable_web_page_preview": False,
    }
    try:
        sender.post_json(url, payload)
    except (URLError, HTTPError, NotificationError) as exc:
        raise NotificationError(_safe_error_detail(exc)) from exc


def send_webhook(notification: Notification, *, webhook_url: str, sender: HttpSender) -> None:
    payload = {
        "text": notification.text(),
        "summary": notification.summary,
        "issue_url": notification.issue_url,
    }
    try:
        sender.post_json(webhook_url, payload)
    except (URLError, HTTPError, NotificationError) as exc:
        raise NotificationError(_safe_error_detail(exc)) from exc


def deliver(
    notification: Notification,
    *,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    webhook_url: str | None,
    sender: HttpSender,
) -> list[ChannelResult]:
    """Attempt delivery to each configured channel independently.

    A channel missing its required secret(s) is reported as not attempted
    (never an error). A channel that is attempted and fails is reported as
    such but never prevents the other channel from being attempted.
    """
    results: list[ChannelResult] = []

    if telegram_bot_token and telegram_chat_id:
        try:
            send_telegram(notification, bot_token=telegram_bot_token, chat_id=telegram_chat_id, sender=sender)
            results.append(ChannelResult("telegram", attempted=True, ok=True))
        except NotificationError as exc:
            results.append(ChannelResult("telegram", attempted=True, ok=False, error=str(exc)))
    else:
        results.append(ChannelResult("telegram", attempted=False, ok=True))

    if webhook_url:
        try:
            send_webhook(notification, webhook_url=webhook_url, sender=sender)
            results.append(ChannelResult("webhook", attempted=True, ok=True))
        except NotificationError as exc:
            results.append(ChannelResult("webhook", attempted=True, ok=False, error=str(exc)))
    else:
        results.append(ChannelResult("webhook", attempted=False, ok=True))

    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-url", required=True, help="URL of the published combined report Issue")
    parser.add_argument("--issue-number", default="", help="Number of the published combined report Issue")
    parser.add_argument("--summary", required=True, help="Short (few-line) summary text, never the full report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    notification = Notification(
        summary=args.summary,
        issue_url=args.issue_url,
        issue_number=args.issue_number or None,
    )

    # Secrets are read only from this process's own environment (GitHub
    # Actions repository secrets in production), never from any repository
    # file. A blank/unset value means "channel not configured".
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID") or None
    webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL") or None

    results = deliver(
        notification,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        webhook_url=webhook_url,
        sender=HttpSender(),
    )

    any_configured = False
    any_failed = False
    for result in results:
        if not result.attempted:
            print(f"{result.name}: not configured, skipped")
            continue
        any_configured = True
        if result.ok:
            print(f"{result.name}: notification sent")
        else:
            any_failed = True
            print(f"{result.name}: delivery failed ({result.error})")

    if not any_configured:
        print("No notification channel configured; nothing to send. GitHub remains the base channel.")

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
