import pytest
from django.urls import reverse

from apps.tables.models import Table
from apps.tables.tests.factories import TableFactory
from apps.users.models import User

pytestmark = pytest.mark.django_db

TABLES_URL = reverse("tables:table-list")


def by_qr_url(table: Table) -> str:
    return reverse("tables:table-by-qr", kwargs={"token": table.qr_token})


class TestPermissions:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (User.Role.MANAGER, 200),
            (User.Role.WAITER, 200),
            (User.Role.COOK, 403),
            (User.Role.CUSTOMER, 403),
        ],
    )
    def test_list(self, client_for, role, expected):
        TableFactory()

        assert client_for(role).get(TABLES_URL).status_code == expected

    def test_anonymous(self, api_client):
        assert api_client.get(TABLES_URL).status_code == 401

    def test_waiter_cannot_create(self, client_for):
        response = client_for(User.Role.WAITER).post(TABLES_URL, {"number": 1, "capacity": 4})

        assert response.status_code == 403


class TestCreate:
    def test_manager_creates_table(self, client_for):
        response = client_for(User.Role.MANAGER).post(
            TABLES_URL, {"number": 11, "capacity": 6, "zone": "terrace"}
        )

        assert response.status_code == 201
        assert response.data["zone_display"] == "Терраса"
        assert response.data["menu_url"].endswith(f"/t/{response.data['qr_token']}/")

    @pytest.mark.parametrize("capacity", [0, 21])
    def test_capacity_out_of_range(self, client_for, capacity):
        response = client_for(User.Role.MANAGER).post(
            TABLES_URL, {"number": 1, "capacity": capacity}
        )

        assert response.status_code == 400
        assert "capacity" in response.data

    def test_duplicate_number(self, client_for):
        TableFactory(number=3)

        response = client_for(User.Role.MANAGER).post(TABLES_URL, {"number": 3, "capacity": 2})

        assert response.status_code == 400
        assert "number" in response.data

    def test_qr_token_is_read_only(self, client_for):
        response = client_for(User.Role.MANAGER).post(
            TABLES_URL,
            {"number": 1, "capacity": 2, "qr_token": "00000000-0000-0000-0000-000000000000"},
        )

        assert response.data["qr_token"] != "00000000-0000-0000-0000-000000000000"


class TestQr:
    def test_manager_downloads_png(self, client_for):
        table = TableFactory(number=4)

        response = client_for(User.Role.MANAGER).get(
            reverse("tables:table-qr", kwargs={"pk": table.pk})
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")
        assert 'filename="table-4-qr.png"' in response["Content-Disposition"]

    def test_waiter_cannot_download(self, client_for):
        table = TableFactory()

        response = client_for(User.Role.WAITER).get(
            reverse("tables:table-qr", kwargs={"pk": table.pk})
        )

        assert response.status_code == 403

    def test_regenerate_invalidates_old_qr(self, api_client, client_for):
        table = TableFactory()
        old_url = by_qr_url(table)

        response = client_for(User.Role.MANAGER).post(
            reverse("tables:table-regenerate-qr", kwargs={"pk": table.pk})
        )

        assert response.status_code == 200
        assert response.data["qr_token"] != str(table.qr_token)
        assert api_client.get(old_url).status_code == 404


class TestPublicByQr:
    def test_guest_sees_minimal_info(self, api_client):
        table = TableFactory(number=9, zone=Table.Zone.VIP, capacity=10)

        response = api_client.get(by_qr_url(table))

        assert response.status_code == 200
        assert response.data == {
            "number": 9,
            "capacity": 10,
            "zone": "vip",
            "zone_display": "VIP-комната",
        }

    def test_inactive_table(self, api_client):
        table = TableFactory(is_active=False)

        assert api_client.get(by_qr_url(table)).status_code == 404
