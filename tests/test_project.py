"""Проверки проекта целиком: health, документация API."""

import pytest
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_health(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_post(client):
    assert client.post(reverse("health")).status_code == 405


def test_openapi_schema_builds(client):
    response = client.get(reverse("schema"))

    assert response.status_code == 200
    assert b"/api/v1/auth/register/" in response.content


def test_swagger_ui(client):
    assert client.get(reverse("swagger-ui")).status_code == 200


def test_openapi_schema_has_no_warnings(tmp_path):
    """Схема строится без предупреждений, иначе `check --deploy` в CI упадёт."""
    call_command("spectacular", "--fail-on-warn", "--file", str(tmp_path / "schema.yml"))
