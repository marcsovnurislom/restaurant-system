import pytest
from django.urls import reverse

from apps.users.models import User
from apps.users.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

REGISTER_URL = reverse("users:register")
TOKEN_URL = reverse("users:token_obtain")
REFRESH_URL = reverse("users:token_refresh")
ME_URL = reverse("users:me")


@pytest.fixture
def register_payload():
    return {
        "username": "aziz",
        "email": "Aziz@Example.com",
        "password": DEFAULT_PASSWORD,
        "phone": "+998901112233",
        "first_name": "Азиз",
    }


class TestRegister:
    def test_creates_customer(self, api_client, register_payload):
        response = api_client.post(REGISTER_URL, register_payload)

        assert response.status_code == 201
        assert response.data["role"] == User.Role.CUSTOMER
        assert "password" not in response.data
        user = User.objects.get(username="aziz")
        assert user.check_password(DEFAULT_PASSWORD)
        assert user.email == "aziz@example.com"

    def test_cannot_register_as_staff(self, api_client, register_payload):
        response = api_client.post(REGISTER_URL, {**register_payload, "role": "admin"})

        assert response.status_code == 201
        assert User.objects.get(username="aziz").role == User.Role.CUSTOMER

    def test_duplicate_email_is_case_insensitive(self, api_client, register_payload):
        UserFactory(email="aziz@example.com")

        response = api_client.post(REGISTER_URL, register_payload)

        assert response.status_code == 400
        assert "email" in response.data

    def test_duplicate_username_is_case_insensitive(self, api_client, register_payload):
        UserFactory(username="AZIZ")

        response = api_client.post(REGISTER_URL, register_payload)

        assert response.status_code == 400
        assert "username" in response.data

    @pytest.mark.parametrize("password", ["12345678", "short", "password123"])
    def test_weak_password_is_rejected(self, api_client, register_payload, password):
        response = api_client.post(REGISTER_URL, {**register_payload, "password": password})

        assert response.status_code == 400
        assert "password" in response.data

    def test_invalid_phone_is_rejected(self, api_client, register_payload):
        response = api_client.post(REGISTER_URL, {**register_payload, "phone": "abc"})

        assert response.status_code == 400
        assert "phone" in response.data


class TestTokens:
    def test_login_returns_token_pair_usable_for_me(self, api_client, user):
        response = api_client.post(
            TOKEN_URL, {"username": user.username, "password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 200
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = api_client.get(ME_URL)
        assert me.status_code == 200
        assert me.data["username"] == user.username

    def test_wrong_password(self, api_client, user):
        response = api_client.post(TOKEN_URL, {"username": user.username, "password": "wrong"})

        assert response.status_code == 401

    def test_refresh_returns_new_access(self, api_client, user):
        tokens = api_client.post(
            TOKEN_URL, {"username": user.username, "password": DEFAULT_PASSWORD}
        ).data

        response = api_client.post(REFRESH_URL, {"refresh": tokens["refresh"]})

        assert response.status_code == 200
        assert "access" in response.data


class TestMe:
    def test_requires_auth(self, api_client):
        assert api_client.get(ME_URL).status_code == 401

    def test_update_profile(self, auth_client, user):
        response = auth_client.patch(ME_URL, {"phone": "+998935554433", "first_name": "Нодира"})

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.phone == "+998935554433"
        assert user.first_name == "Нодира"

    def test_role_and_email_are_read_only(self, auth_client, user):
        auth_client.patch(ME_URL, {"role": "admin", "email": "hacker@example.com"})

        user.refresh_from_db()
        assert user.role == User.Role.CUSTOMER
        assert user.email != "hacker@example.com"

    def test_put_is_not_allowed(self, auth_client):
        assert auth_client.put(ME_URL, {}).status_code == 405
