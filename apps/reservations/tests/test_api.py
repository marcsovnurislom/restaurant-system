import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.reservations.models import Reservation
from apps.reservations.tests.factories import ReservationFactory, future_slot
from apps.tables.tests.factories import TableFactory
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("reservations-api:reservation-list")
MY_URL = reverse("reservations-api:reservation-my")
AVAILABILITY_URL = reverse("reservations-api:reservation-availability")


def detail_url(reservation: Reservation, action: str = "detail") -> str:
    return reverse(f"reservations-api:reservation-{action}", kwargs={"pk": reservation.pk})


def client_as(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def payload():
    return {
        "start_at": future_slot().isoformat(),
        "guests_count": 2,
        "guest_name": "Нодира",
        "phone": "+998935554433",
        "email": "nodira@example.com",
        "comment": "У окна, если можно",
    }


class TestAvailability:
    def test_returns_free_times(self, api_client):
        TableFactory()
        day = timezone.localdate() + timedelta(days=2)

        response = api_client.get(AVAILABILITY_URL, {"date": day.isoformat(), "guests": 2})

        assert response.status_code == 200
        assert response.data["slots"][0] == "10:00"
        assert response.data["slots"][-1] == "21:00"

    @pytest.mark.parametrize("params", [{}, {"date": "завтра", "guests": 2}, {"guests": 0}])
    def test_invalid_params(self, api_client, params):
        assert api_client.get(AVAILABILITY_URL, params).status_code == 400


class TestCreate:
    def test_anonymous_guest_books_table(self, api_client, payload):
        table = TableFactory(number=5)

        response = api_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 201
        assert response.data["table_number"] == 5
        assert response.data["status"] == "confirmed"
        assert response.data["token"]
        assert Reservation.objects.get().table == table

    def test_logged_in_guest_sees_booking_in_my(self, payload):
        TableFactory()
        client = client_as(UserFactory())

        client.post(LIST_URL, payload, format="json")
        response = client.get(MY_URL)

        assert response.data["count"] == 1

    def test_invalid_time(self, api_client, payload):
        TableFactory()

        response = api_client.post(
            LIST_URL, {**payload, "start_at": future_slot(hour=22).isoformat()}, format="json"
        )

        assert response.status_code == 400
        assert "detail" in response.data

    def test_no_free_tables_is_conflict(self, api_client, payload):
        ReservationFactory(table=TableFactory(), start_at=future_slot())

        response = api_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 409

    def test_invalid_phone(self, api_client, payload):
        response = api_client.post(LIST_URL, {**payload, "phone": "123"}, format="json")

        assert response.status_code == 400
        assert "phone" in response.data


class TestStaffList:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (User.Role.MANAGER, 200),
            (User.Role.WAITER, 200),
            (User.Role.COOK, 403),
            (User.Role.CUSTOMER, 403),
        ],
    )
    def test_permissions(self, client_for, role, expected):
        assert client_for(role).get(LIST_URL).status_code == expected

    def test_filter_by_date(self, client_for):
        tomorrow = ReservationFactory(start_at=future_slot(days=1))
        ReservationFactory(start_at=future_slot(days=3))

        response = client_for(User.Role.WAITER).get(
            LIST_URL, {"date": timezone.localdate(tomorrow.start_at).isoformat()}
        )

        assert [item["id"] for item in response.data["results"]] == [tomorrow.id]


class TestOwnership:
    def test_owner_sees_own_reservation(self):
        owner = UserFactory()
        reservation = ReservationFactory(user=owner)

        assert client_as(owner).get(detail_url(reservation)).status_code == 200

    def test_other_guest_gets_404(self):
        reservation = ReservationFactory(user=UserFactory())

        assert client_as(UserFactory()).get(detail_url(reservation)).status_code == 404

    def test_owner_cancels(self):
        owner = UserFactory()
        reservation = ReservationFactory(user=owner)

        response = client_as(owner).post(detail_url(reservation, "cancel"))

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"

    def test_other_guest_cannot_cancel(self):
        reservation = ReservationFactory(user=UserFactory())

        response = client_as(UserFactory()).post(detail_url(reservation, "cancel"))

        assert response.status_code == 404
        reservation.refresh_from_db()
        assert reservation.status == Reservation.Status.CONFIRMED

    def test_cancel_twice_is_400(self):
        owner = UserFactory()
        reservation = ReservationFactory(user=owner, status=Reservation.Status.CANCELLED)

        assert client_as(owner).post(detail_url(reservation, "cancel")).status_code == 400

    def test_anonymous_cannot_use_id_endpoints(self, api_client):
        reservation = ReservationFactory()

        assert api_client.post(detail_url(reservation, "cancel")).status_code == 401


class TestSetStatus:
    def test_waiter_marks_arrival(self, client_for):
        reservation = ReservationFactory()

        response = client_for(User.Role.WAITER).post(
            detail_url(reservation, "set-status"), {"status": "completed"}
        )

        assert response.status_code == 200
        assert response.data["status_display"] == "Гость пришёл"

    def test_customer_cannot(self):
        owner = UserFactory()
        reservation = ReservationFactory(user=owner)

        response = client_as(owner).post(
            detail_url(reservation, "set-status"), {"status": "completed"}
        )

        assert response.status_code == 403

    def test_unknown_status(self, client_for):
        response = client_for(User.Role.WAITER).post(
            detail_url(ReservationFactory(), "set-status"), {"status": "cancelled"}
        )

        assert response.status_code == 400


class TestByToken:
    def test_guest_views_by_token(self, api_client):
        reservation = ReservationFactory()

        response = api_client.get(
            reverse("reservations-api:by-token", kwargs={"token": reservation.token})
        )

        assert response.status_code == 200
        assert response.data["id"] == reservation.id

    def test_guest_cancels_by_token(self, api_client):
        reservation = ReservationFactory()

        response = api_client.post(
            reverse("reservations-api:by-token-cancel", kwargs={"token": reservation.token})
        )

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"

    def test_unknown_token(self, api_client):
        url = reverse("reservations-api:by-token", kwargs={"token": uuid.uuid4()})

        assert api_client.get(url).status_code == 404
