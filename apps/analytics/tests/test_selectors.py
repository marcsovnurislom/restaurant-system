from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.analytics import selectors
from apps.analytics.selectors import Period
from apps.menu.tests.factories import DishFactory
from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.reservations.models import Reservation
from apps.reservations.tests.factories import ReservationFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()
PERIOD = Period(TODAY - timedelta(days=6), TODAY)


def at(day_offset: int, hour: int = 13) -> datetime:
    """Момент в часовом поясе ресторана: day_offset дней назад, в hour часов."""
    day = TODAY - timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(day, time(hour)))


def order(*, price: str = "30000", status=Order.Status.COMPLETED, when=None, dishes=None):
    created = make_order(dishes=dishes or [DishFactory(price=Decimal(price))])
    Order.objects.filter(pk=created.pk).update(status=status, created_at=when or at(0))
    return created


class TestPeriod:
    def test_days_and_previous(self):
        period = Period(TODAY - timedelta(days=6), TODAY)

        assert period.days == 7
        assert period.previous() == Period(TODAY - timedelta(days=13), TODAY - timedelta(days=7))

    def test_bounds_are_local_midnights(self):
        start, end = PERIOD.bounds

        assert timezone.localtime(start).time() == time(0)
        assert end - start == timedelta(days=7)


class TestSummary:
    def test_counts_only_completed_revenue(self):
        order(price="40000")
        order(price="60000")
        order(price="99000", status=Order.Status.CANCELLED)
        order(price="99000", status=Order.Status.COOKING)

        result = selectors.summary(PERIOD)

        assert result["revenue"] == Decimal("100000")
        assert result["orders_completed"] == 2
        assert result["average_check"] == Decimal("50000")
        assert result["cancel_rate"] == 0.25

    def test_outside_period_is_ignored(self):
        order(when=at(10))

        assert selectors.summary(PERIOD)["orders_completed"] == 0

    def test_no_show_rate(self):
        start = at(1, hour=19)
        for status in (
            Reservation.Status.COMPLETED,
            Reservation.Status.COMPLETED,
            Reservation.Status.NO_SHOW,
            Reservation.Status.CANCELLED,
        ):
            ReservationFactory(start_at=start, end_at=start + timedelta(hours=2), status=status)

        result = selectors.summary(PERIOD)

        assert result["reservations"] == 4
        # Отменённые не считаются: неявка — 1 из 3 состоявшихся визитов
        assert result["no_show_rate"] == pytest.approx(1 / 3, abs=1e-4)

    def test_empty_period(self):
        result = selectors.summary(PERIOD)

        assert result["revenue"] == 0
        assert result["average_check"] == 0
        assert result["cancel_rate"] == 0.0


def test_revenue_by_day_fills_gaps():
    order(price="10000", when=at(0))
    order(price="15000", when=at(0))
    order(price="20000", when=at(2))

    rows = selectors.revenue_by_day(PERIOD)

    assert len(rows) == 7
    assert rows[-1] == {"date": TODAY, "orders": 2, "revenue": Decimal("25000")}
    assert rows[-3]["revenue"] == Decimal("20000")
    assert rows[0] == {"date": PERIOD.date_from, "orders": 0, "revenue": 0}


def test_revenue_uses_restaurant_timezone():
    """Заказ в 00:30 по Ташкенту — это 19:30 предыдущего дня по UTC. Он относится к своему дню."""
    order(when=at(0, hour=0) + timedelta(minutes=30))

    rows = selectors.revenue_by_day(PERIOD)

    assert rows[-1]["orders"] == 1
    assert rows[-2]["orders"] == 0


def test_top_dishes_ranked_by_revenue():
    plov = DishFactory(name="Плов", price=Decimal("55000"))
    samsa = DishFactory(name="Самса", price=Decimal("12000"))
    order(dishes=[plov, samsa])
    order(dishes=[samsa])
    order(dishes=[plov], status=Order.Status.CANCELLED)

    rows = selectors.top_dishes(PERIOD)

    assert [(row["rank"], row["name"], row["quantity"]) for row in rows] == [
        (1, "Плов", 1),
        (2, "Самса", 2),
    ]
    assert rows[0]["revenue"] == Decimal("55000")
    assert rows[1]["revenue"] == Decimal("24000")


def test_top_dishes_limit():
    order(dishes=DishFactory.create_batch(5))

    assert len(selectors.top_dishes(PERIOD, limit=3)) == 3


def test_hourly_load():
    order(when=at(0, hour=13))
    order(when=at(1, hour=13))
    order(when=at(0, hour=19))
    order(when=at(0, hour=19), status=Order.Status.CANCELLED)

    rows = selectors.hourly_load(PERIOD)

    assert len(rows) == 24
    assert rows[13] == {"hour": 13, "orders": 2}
    assert rows[19] == {"hour": 19, "orders": 1}


def test_query_counts(django_assert_num_queries):
    for _ in range(5):
        order(dishes=DishFactory.create_batch(2))

    with django_assert_num_queries(2):
        selectors.summary(PERIOD)
    with django_assert_num_queries(1):
        selectors.revenue_by_day(PERIOD)
    with django_assert_num_queries(1):
        selectors.top_dishes(PERIOD)
    with django_assert_num_queries(1):
        selectors.hourly_load(PERIOD)
