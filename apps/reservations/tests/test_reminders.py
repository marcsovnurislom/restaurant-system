from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.services import reservation_send_due_reminders
from apps.reservations.tasks import send_reservation_reminders
from apps.reservations.tests.factories import ReservationFactory

pytestmark = pytest.mark.django_db


def reservation_in(minutes: int, **kwargs) -> Reservation:
    start = timezone.now() + timedelta(minutes=minutes)
    return ReservationFactory(
        start_at=start, end_at=start + timedelta(hours=2), email="guest@example.com", **kwargs
    )


def test_sends_reminder_for_upcoming_reservation(settings):
    settings.SITE_URL = "https://bahor.uz"
    reservation = reservation_in(90)

    assert send_reservation_reminders() == 1

    reservation.refresh_from_db()
    assert reservation.reminder_sent_at is not None
    assert mail.outbox[0].to == ["guest@example.com"]
    assert f"https://bahor.uz/reservations/{reservation.token}/" in mail.outbox[0].body


def test_does_not_send_twice():
    reservation_in(90)

    reservation_send_due_reminders()
    reservation_send_due_reminders()

    assert len(mail.outbox) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minutes": 180},
        {"minutes": -10},
        {"minutes": 60, "status": Reservation.Status.CANCELLED},
        {"minutes": 60, "email": ""},
    ],
    ids=["too-early", "already-started", "cancelled", "no-email"],
)
def test_skips(kwargs):
    minutes = kwargs.pop("minutes")
    start = timezone.now() + timedelta(minutes=minutes)
    ReservationFactory(
        start_at=start,
        end_at=start + timedelta(hours=2),
        email=kwargs.pop("email", "guest@example.com"),
        **kwargs,
    )

    assert reservation_send_due_reminders() == 0
    assert mail.outbox == []


def test_one_failed_email_does_not_block_others(monkeypatch):
    failing, ok = reservation_in(60), reservation_in(70)
    real_send = mail.send_mail

    def flaky_send(*args, recipient_list, **kwargs):
        if recipient_list == [failing.email] and not flaky_send.failed:
            flaky_send.failed = True
            raise ConnectionError("SMTP недоступен")
        return real_send(*args, recipient_list=recipient_list, **kwargs)

    flaky_send.failed = False
    monkeypatch.setattr("apps.reservations.services.send_mail", flaky_send)

    assert reservation_send_due_reminders() == 1

    failing.refresh_from_db()
    ok.refresh_from_db()
    assert failing.reminder_sent_at is None
    assert ok.reminder_sent_at is not None
    # При следующем запуске упавшее письмо уйдёт
    assert reservation_send_due_reminders() == 1
