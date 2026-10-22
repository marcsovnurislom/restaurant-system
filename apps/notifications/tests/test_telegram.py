import json
import urllib.error

import pytest

from apps.notifications.telegram import TelegramError, send_telegram_message


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def configured(settings):
    settings.TELEGRAM_BOT_TOKEN = "123:test-token"
    settings.TELEGRAM_CHAT_ID = "42"


def test_not_configured_only_logs(settings, caplog):
    settings.TELEGRAM_BOT_TOKEN = ""
    caplog.set_level("INFO")

    assert send_telegram_message("Привет") is False
    assert "Привет" in caplog.text


def test_sends_html_message(configured, monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent.update(url=request.full_url, body=json.loads(request.data), timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert send_telegram_message("<b>Заказ</b>") is True
    assert sent["url"] == "https://api.telegram.org/bot123:test-token/sendMessage"
    assert sent["body"] == {
        "chat_id": "42",
        "text": "<b>Заказ</b>",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    assert sent["timeout"] == 10


@pytest.mark.parametrize("code", [500, 502, 429])
def test_temporary_errors_are_retryable(configured, monkeypatch, code):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, code, "error", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", fail)

    with pytest.raises(TelegramError):
        send_telegram_message("x")


def test_client_error_is_not_retried(configured, monkeypatch):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 400, "bad chat", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", fail)

    assert send_telegram_message("x") is False


def test_network_error_is_retryable(configured, monkeypatch):
    def fail(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fail)

    with pytest.raises(TelegramError):
        send_telegram_message("x")
