"""Страницы бронирования на сайте."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.tests.factories import ReservationFactory, future_slot
from apps.tables.tests.factories import TableFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

CREATE_URL = reverse("reservations:create")


@pytest.fixture
def form_data():
    start = timezone.localtime(future_slot())
    return {
        "date": start.date().isoformat(),
        "time": "19:00",
        "guests_count": 2,
        "guest_name": "Нодира",
        "phone": "+998935554433",
    }


def test_form_page(client):
    response = client.get(CREATE_URL)

    assert response.status_code == 200
    assert "Забронировать стол" in response.content.decode()


def test_form_prefilled_for_logged_in_user(client):
    user = UserFactory(first_name="Азиз", last_name="Каримов", phone="+998901112233")
    client.force_login(user)

    form = client.get(CREATE_URL).context["form"]

    assert form.initial["guest_name"] == "Азиз Каримов"
    assert form.initial["phone"] == "+998901112233"


def test_successful_booking_redirects_to_confirmation(client, form_data):
    TableFactory(number=3)

    response = client.post(CREATE_URL, form_data, follow=True)

    reservation = Reservation.objects.get()
    assert response.redirect_chain[-1][0] == reverse(
        "reservations:detail", kwargs={"token": reservation.token}
    )
    html = response.content.decode()
    assert "Стол забронирован" in html
    assert "№3" in html


def test_no_tables_shows_error_on_form(client, form_data):
    ReservationFactory(table=TableFactory(), start_at=future_slot())

    response = client.post(CREATE_URL, form_data)

    assert response.status_code == 200
    assert "все подходящие столы заняты" in response.content.decode()
    assert Reservation.objects.count() == 1


def test_invalid_phone(client, form_data):
    TableFactory()

    response = client.post(CREATE_URL, {**form_data, "phone": "abc"})

    assert response.status_code == 200
    assert response.context["form"].errors["phone"]


def test_detail_page_has_cancel_button(client):
    reservation = ReservationFactory()

    response = client.get(reverse("reservations:detail", kwargs={"token": reservation.token}))

    assert "Отменить бронь" in response.content.decode()


def test_cancel_from_site(client):
    reservation = ReservationFactory()

    response = client.post(
        reverse("reservations:cancel", kwargs={"token": reservation.token}), follow=True
    )

    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CANCELLED
    html = response.content.decode()
    assert "Бронь отменена" in html
    assert "Отменить бронь" not in html


def test_cancel_inactive_shows_error(client):
    reservation = ReservationFactory(status=Reservation.Status.CANCELLED)

    response = client.post(
        reverse("reservations:cancel", kwargs={"token": reservation.token}), follow=True
    )

    assert "уже не активна" in response.content.decode()
