from datetime import datetime, time, timedelta

import factory
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.rules import DURATION
from apps.tables.tests.factories import TableFactory


def future_slot(days: int = 2, hour: int = 19, minute: int = 0) -> datetime:
    """Время слота через `days` дней в часовом поясе ресторана."""
    day = timezone.localdate() + timedelta(days=days)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class ReservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reservation

    table = factory.SubFactory(TableFactory)
    guest_name = "Азиз"
    phone = "+998901234567"
    guests_count = 2
    start_at = factory.LazyFunction(future_slot)
    end_at = factory.LazyAttribute(lambda o: o.start_at + DURATION)
