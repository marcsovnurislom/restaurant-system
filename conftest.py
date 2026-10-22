import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """Кэш общий для всех тестов: счётчики попыток входа не должны переходить из теста в тест."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def client_for(db):
    """API-клиент от имени пользователя с ролью: client_for(User.Role.COOK)."""

    def make(role: str) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=UserFactory(role=role))
        return client

    return make
