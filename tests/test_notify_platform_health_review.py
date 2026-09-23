from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import notify_platform_health_review as notify  # noqa: E402

FAKE_SECRET = "FAKE-SUPER-SECRET-TOKEN-123"  # noqa: S105 - test fixture only, not a real credential
FAKE_WEBHOOK = "https://example.invalid/hooks/FAKE-WEBHOOK-SECRET-456"


class FakeSender:
    """Records calls instead of making a real network call."""

    def __init__(self, *, fail_urls: set[str] | None = None, raise_message: str | None = None) -> None:
        self.fail_urls = fail_urls or set()
        self.raise_message = raise_message
        self.calls: list[tuple[str, dict]] = []

    def post_json(self, url: str, payload: dict, *, timeout: float = 10.0) -> None:
        self.calls.append((url, payload))
        if url in self.fail_urls:
            raise notify.NotificationError(self.raise_message or "boom")


def _notification() -> notify.Notification:
    return notify.Notification(
        summary="Platform Health Review published.",
        issue_url="https://github.com/lehard/dev-platform/issues/101",
        issue_number="101",
    )


class NotificationTextTests(unittest.TestCase):
    def test_combines_summary_and_link(self) -> None:
        text = _notification().text()
        self.assertIn("Platform Health Review published.", text)
        self.assertIn("https://github.com/lehard/dev-platform/issues/101", text)

    def test_falls_back_to_summary_only_when_link_missing(self) -> None:
        n = notify.Notification(summary="hello", issue_url="")
        self.assertEqual(n.text(), "hello")


class DeliverTests(unittest.TestCase):
    def test_both_channels_configured_sends_to_both(self) -> None:
        sender = FakeSender()
        results = notify.deliver(
            _notification(),
            telegram_bot_token="tok",
            telegram_chat_id="chat",
            webhook_url="https://hooks.example/x",
            sender=sender,
        )
        by_name = {r.name: r for r in results}
        self.assertTrue(by_name["telegram"].attempted)
        self.assertTrue(by_name["telegram"].ok)
        self.assertTrue(by_name["webhook"].attempted)
        self.assertTrue(by_name["webhook"].ok)
        self.assertEqual(len(sender.calls), 2)

    def test_only_telegram_configured_skips_webhook(self) -> None:
        sender = FakeSender()
        results = notify.deliver(
            _notification(),
            telegram_bot_token="tok",
            telegram_chat_id="chat",
            webhook_url=None,
            sender=sender,
        )
        by_name = {r.name: r for r in results}
        self.assertTrue(by_name["telegram"].attempted)
        self.assertFalse(by_name["webhook"].attempted)
        self.assertTrue(by_name["webhook"].ok)  # not-configured is not an error
        self.assertEqual(len(sender.calls), 1)

    def test_only_webhook_configured_skips_telegram(self) -> None:
        sender = FakeSender()
        results = notify.deliver(
            _notification(),
            telegram_bot_token=None,
            telegram_chat_id=None,
            webhook_url="https://hooks.example/x",
            sender=sender,
        )
        by_name = {r.name: r for r in results}
        self.assertFalse(by_name["telegram"].attempted)
        self.assertTrue(by_name["telegram"].ok)
        self.assertTrue(by_name["webhook"].attempted)
        self.assertTrue(by_name["webhook"].ok)
        self.assertEqual(len(sender.calls), 1)

    def test_neither_configured_is_a_clean_no_op(self) -> None:
        sender = FakeSender()
        results = notify.deliver(
            _notification(),
            telegram_bot_token=None,
            telegram_chat_id=None,
            webhook_url=None,
            sender=sender,
        )
        self.assertTrue(all(not r.attempted and r.ok for r in results))
        self.assertEqual(sender.calls, [])

    def test_partial_telegram_secret_is_treated_as_not_configured(self) -> None:
        # Only the token without a chat id (or vice versa) must not attempt
        # delivery -- Telegram requires both to address a message.
        sender = FakeSender()
        results = notify.deliver(
            _notification(),
            telegram_bot_token="tok",
            telegram_chat_id=None,
            webhook_url=None,
            sender=sender,
        )
        by_name = {r.name: r for r in results}
        self.assertFalse(by_name["telegram"].attempted)
        self.assertEqual(sender.calls, [])

    def test_one_channel_failing_does_not_block_the_other(self) -> None:
        sender = FakeSender(fail_urls={"https://api.telegram.org/bottok/sendMessage"})
        results = notify.deliver(
            _notification(),
            telegram_bot_token="tok",
            telegram_chat_id="chat",
            webhook_url="https://hooks.example/x",
            sender=sender,
        )
        by_name = {r.name: r for r in results}
        self.assertTrue(by_name["telegram"].attempted)
        self.assertFalse(by_name["telegram"].ok)
        self.assertTrue(by_name["webhook"].attempted)
        self.assertTrue(by_name["webhook"].ok)
        # Both channels were still attempted despite telegram's failure.
        self.assertEqual(len(sender.calls), 2)

    def test_webhook_failing_does_not_block_telegram(self) -> None:
        sender = FakeSender(fail_urls={"https://hooks.example/x"})
        results = notify.deliver(
            _notification(),
            telegram_bot_token="tok",
            telegram_chat_id="chat",
            webhook_url="https://hooks.example/x",
            sender=sender,
        )
        by_name = {r.name: r for r in results}
        self.assertTrue(by_name["telegram"].ok)
        self.assertFalse(by_name["webhook"].ok)


class SecretRedactionTests(unittest.TestCase):
    def test_safe_error_detail_never_returns_raw_exception_text(self) -> None:
        exc = notify.NotificationError(f"contains secret {FAKE_SECRET} and url {FAKE_WEBHOOK}")
        detail = notify._safe_error_detail(exc)
        self.assertNotIn(FAKE_SECRET, detail)
        self.assertNotIn(FAKE_WEBHOOK, detail)
        self.assertEqual(detail, "NotificationError")

    def test_failure_message_surfaced_to_caller_excludes_secret(self) -> None:
        # Even when the underlying fake sender's exception message embeds a
        # secret-looking value (simulating a worst-case HTTP client message),
        # the ChannelResult error text must not leak it.
        sender = FakeSender(
            fail_urls={"https://api.telegram.org/bottok/sendMessage"},
            raise_message=f"leaked {FAKE_SECRET}",
        )
        results = notify.deliver(
            _notification(),
            telegram_bot_token="tok",
            telegram_chat_id="chat",
            webhook_url=None,
            sender=sender,
        )
        telegram_result = next(r for r in results if r.name == "telegram")
        self.assertFalse(telegram_result.ok)
        self.assertNotIn(FAKE_SECRET, telegram_result.error or "")

    def test_main_stdout_never_contains_configured_secrets(self) -> None:
        # Full main() run with secrets present in the environment; assert
        # nothing printed to stdout ever contains the secret values.
        import os
        import unittest.mock as mock

        env = {
            "TELEGRAM_BOT_TOKEN": FAKE_SECRET,
            "TELEGRAM_CHAT_ID": "123456",
            "NOTIFY_WEBHOOK_URL": FAKE_WEBHOOK,
        }
        sender_holder: dict[str, FakeSender] = {}

        def fake_http_sender() -> FakeSender:
            sender = FakeSender()
            sender_holder["sender"] = sender
            return sender

        buf = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(notify, "HttpSender", fake_http_sender):
                with redirect_stdout(buf):
                    exit_code = notify.main(
                        [
                            "--issue-url",
                            "https://github.com/lehard/dev-platform/issues/101",
                            "--issue-number",
                            "101",
                            "--summary",
                            "Platform Health Review published.",
                        ]
                    )
        output = buf.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertNotIn(FAKE_SECRET, output)
        self.assertNotIn(FAKE_WEBHOOK, output)
        self.assertNotIn("123456", output)


class MainCleanNoOpTests(unittest.TestCase):
    def test_main_with_no_secrets_configured_is_clean_no_op(self) -> None:
        import os
        import unittest.mock as mock

        buf = io.StringIO()
        env_without_secrets = {
            k: v
            for k, v in os.environ.items()
            if k not in {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "NOTIFY_WEBHOOK_URL"}
        }
        with mock.patch.dict(os.environ, env_without_secrets, clear=True):
            with redirect_stdout(buf):
                exit_code = notify.main(
                    [
                        "--issue-url",
                        "https://github.com/lehard/dev-platform/issues/101",
                        "--issue-number",
                        "101",
                        "--summary",
                        "Platform Health Review published.",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertIn("No notification channel configured", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
