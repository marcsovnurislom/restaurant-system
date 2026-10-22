"""Поведение, которое важно только в продакшене за reverse-proxy."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import SimpleRateThrottle

from apps.users.models import User
from apps.users.tests.factories import DEFAULT_PASSWORD, UserFactory

BASE_DIR = Path(__file__).resolve().parent.parent
PROD_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.prod",
    "DJANGO_SECRET_KEY": "test-only-secret-key-that-is-long-enough-1234567890",
    "DJANGO_ALLOWED_HOSTS": "bahor.uz",
    "REDIS_URL": "redis://redis:6379/0",
}


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["bahor.uz"], SECURE_SSL_REDIRECT=True)
def test_health_check_works_from_inside_container(client):
    """Docker стучится по http://127.0.0.1 — без HTTPS и не с боевым доменом."""
    response = client.get("/health/", HTTP_HOST="127.0.0.1:8000")

    assert response.status_code == 200
    # Остальные страницы с чужим Host по-прежнему отклоняются
    assert client.get("/", HTTP_HOST="127.0.0.1:8000").status_code == 400


@pytest.mark.django_db
def test_custom_404(client):
    response = client.get("/net-takoy-stranicy/")

    assert response.status_code == 404
    assert "Страница не найдена" in response.content.decode()


def test_admin_url_comes_from_settings(settings):
    assert reverse("admin:index") == f"/{settings.ADMIN_URL}"


@pytest.mark.django_db
class TestStaffLoginLockout:
    URL = "/staff/login/"

    @pytest.fixture(autouse=True)
    def small_limit(self, settings):
        settings.LOGIN_ATTEMPTS_LIMIT = 3

    def login(self, client, password, ip="10.0.0.1"):
        return client.post(self.URL, {"username": "cook", "password": password}, REMOTE_ADDR=ip)

    def test_locks_after_failed_attempts_even_with_right_password(self, client):
        UserFactory(username="cook", role=User.Role.COOK)
        for _ in range(3):
            assert self.login(client, "wrong").status_code == 200

        response = self.login(client, DEFAULT_PASSWORD)

        assert response.status_code == 429
        assert "Слишком много неудачных попыток" in response.content.decode()
        assert "_auth_user_id" not in client.session

    def test_other_ip_is_not_locked(self, client):
        UserFactory(username="cook", role=User.Role.COOK)
        for _ in range(3):
            self.login(client, "wrong")

        response = self.login(client, DEFAULT_PASSWORD, ip="10.0.0.2")

        assert response.status_code == 302

    def test_success_resets_counter(self, client):
        UserFactory(username="cook", role=User.Role.COOK)
        for _ in range(2):
            self.login(client, "wrong")
        self.login(client, DEFAULT_PASSWORD)
        client.logout()

        for _ in range(2):
            self.login(client, "wrong")

        assert self.login(client, DEFAULT_PASSWORD).status_code == 302


def test_throttle_uses_proxy_ip_not_spoofed_header():
    """С NUM_PROXIES=1 подделанный клиентом X-Forwarded-For не меняет IP для лимитов."""
    request = APIRequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.7", REMOTE_ADDR="172.18.0.5"
    )

    class AnyThrottle(SimpleRateThrottle):
        rate = "10/minute"

    with override_settings(REST_FRAMEWORK={"NUM_PROXIES": 1}):
        ident = AnyThrottle().get_ident(request)

    # Последний адрес добавил наш Caddy — это и есть настоящий клиент
    assert ident == "203.0.113.7"


def run_with_prod_settings(code: str, **extra_env) -> subprocess.CompletedProcess:
    env = {**os.environ, **PROD_ENV, **extra_env}
    return subprocess.run(  # noqa: S603 — фиксированная команда, без пользовательского ввода
        [sys.executable, "-c", f"import django; django.setup(); {code}"],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_prod_settings_use_shared_cache_and_proxy_count():
    result = run_with_prod_settings(
        "import json; from django.conf import settings; print(json.dumps(["
        "settings.CACHES['default']['LOCATION'], settings.REST_FRAMEWORK['NUM_PROXIES'],"
        "settings.DEBUG, settings.PAYMENT_PROVIDER]))"
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["redis://redis:6379/1", 1, False, "stripe"]


def test_prod_refuses_fake_payments():
    result = run_with_prod_settings("pass", PAYMENT_PROVIDER="fake")

    assert result.returncode != 0
    assert "PAYMENT_PROVIDER=fake" in result.stderr


def test_prod_requires_secret_key():
    env_without_key = {key: value for key, value in PROD_ENV.items() if key != "DJANGO_SECRET_KEY"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BASE_DIR,
        env={k: v for k, v in os.environ.items() if k != "DJANGO_SECRET_KEY"} | env_without_key,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr
