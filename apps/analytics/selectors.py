"""Отчёты для владельца. Все расчёты — агрегатами в БД, без циклов по заказам в Python.

Выручка считается только по выполненным заказам: отменённые и ещё
не выданные деньги ресторану не принесли.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, F, Q, QuerySet, Sum, Window
from django.db.models.functions import ExtractHour, RowNumber, TruncDate
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.reservations.models import Reservation

ZERO = Decimal("0")


@dataclass(frozen=True)
class Period:
    date_from: date
    date_to: date

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    @property
    def bounds(self) -> tuple[datetime, datetime]:
        """[начало первого дня, начало дня после последнего) в часовом поясе ресторана."""
        start = timezone.make_aware(datetime.combine(self.date_from, time.min))
        end = timezone.make_aware(datetime.combine(self.date_to + timedelta(days=1), time.min))
        return start, end

    def previous(self) -> "Period":
        """Такой же по длине период прямо перед этим — для сравнения «было/стало»."""
        return Period(
            self.date_from - timedelta(days=self.days), self.date_from - timedelta(days=1)
        )

    @classmethod
    def last_days(cls, days: int, *, today: date | None = None) -> "Period":
        today = today or timezone.localdate()
        return cls(today - timedelta(days=days - 1), today)


def _orders(period: Period) -> QuerySet[Order]:
    start, end = period.bounds
    return Order.objects.filter(created_at__gte=start, created_at__lt=end)


def summary(period: Period) -> dict:
    """Главные цифры за период: 2 запроса (заказы и брони)."""
    completed = Q(status=Order.Status.COMPLETED)
    # Имена агрегатов не должны совпадать с полями модели (у Order есть поле total),
    # иначе Django примет поле за агрегат: "Cannot compute Sum('total')"
    orders = _orders(period).aggregate(
        orders_count=Count("id"),
        completed_count=Count("id", filter=completed),
        cancelled_count=Count("id", filter=Q(status=Order.Status.CANCELLED)),
        revenue=Sum("total", filter=completed),
        average_check=Avg("total", filter=completed),
    )
    start, end = period.bounds
    reservations = Reservation.objects.filter(start_at__gte=start, start_at__lt=end).aggregate(
        reservations_count=Count("id"),
        visited_count=Count("id", filter=Q(status=Reservation.Status.COMPLETED)),
        no_show_count=Count("id", filter=Q(status=Reservation.Status.NO_SHOW)),
    )
    finished_visits = reservations["visited_count"] + reservations["no_show_count"]
    return {
        "revenue": orders["revenue"] or ZERO,
        "orders_completed": orders["completed_count"],
        "average_check": (orders["average_check"] or ZERO).quantize(Decimal("1")),
        "cancel_rate": _ratio(orders["cancelled_count"], orders["orders_count"]),
        "reservations": reservations["reservations_count"],
        "no_show_rate": _ratio(reservations["no_show_count"], finished_visits),
    }


def revenue_by_day(period: Period) -> list[dict]:
    """Выручка и число заказов по дням. Дни без заказов — нули, чтобы на графике не было дыр."""
    rows = (
        _orders(period)
        .filter(status=Order.Status.COMPLETED)
        # TruncDate режет дату в часовом поясе ресторана, а не в UTC:
        # заказ в 01:00 по Ташкенту относится к своему дню, а не к вчерашнему
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(orders=Count("id"), revenue=Sum("total"))
        .order_by("day")
    )
    by_day = {row["day"]: row for row in rows}
    result = []
    for offset in range(period.days):
        day = period.date_from + timedelta(days=offset)
        row = by_day.get(day, {})
        result.append(
            {"date": day, "orders": row.get("orders", 0), "revenue": row.get("revenue") or ZERO}
        )
    return result


def top_dishes(period: Period, *, limit: int = 10) -> list[dict]:
    """Самые прибыльные блюда. Место в рейтинге считает оконная функция ROW_NUMBER()."""
    start, end = period.bounds
    line_revenue = Sum(
        F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2)
    )
    rows = (
        OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED,
            order__created_at__gte=start,
            order__created_at__lt=end,
        )
        .values("dish_id", "dish__name")
        .annotate(units=Sum("quantity"), revenue=line_revenue)
        .annotate(rank=Window(RowNumber(), order_by=[F("revenue").desc(), F("dish__name").asc()]))
        .order_by("rank")[:limit]
    )
    return [
        {
            "rank": row["rank"],
            "dish_id": row["dish_id"],
            "name": row["dish__name"],
            "quantity": row["units"],
            "revenue": row["revenue"],
        }
        for row in rows
    ]


def hourly_load(period: Period) -> list[dict]:
    """Сколько заказов приходит в каждый час суток — для планирования смен."""
    rows = (
        _orders(period)
        .exclude(status=Order.Status.CANCELLED)
        .annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(orders=Count("id"))
    )
    by_hour = {row["hour"]: row["orders"] for row in rows}
    return [{"hour": hour, "orders": by_hour.get(hour, 0)} for hour in range(24)]


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0
