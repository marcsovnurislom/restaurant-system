from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.analytics import selectors
from apps.analytics.api.serializers import DEFAULT_DAYS, PeriodSerializer
from apps.analytics.selectors import Period
from apps.kitchen.views import staff_required
from apps.users.models import User

PRESETS = (7, 30, 90)


@require_GET
@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    if not request.user.has_role(User.Role.MANAGER):
        raise PermissionDenied

    form = PeriodSerializer(data=request.GET)
    period = form.validated_data["period"] if form.is_valid() else Period.last_days(DEFAULT_DAYS)
    current, previous = selectors.summary(period), selectors.summary(period.previous())
    revenue = selectors.revenue_by_day(period)
    hourly = selectors.hourly_load(period)
    top = selectors.top_dishes(period)
    top_max = max((row["revenue"] for row in top), default=Decimal("0"))

    context = {
        "period": period,
        "period_error": None if form.is_valid() else "; ".join(_errors(form.errors)),
        "presets": [(days, Period.last_days(days)) for days in PRESETS],
        "kpis": [
            _kpi("Выручка", current["revenue"], previous["revenue"], "money"),
            _kpi("Выполнено заказов", current["orders_completed"], previous["orders_completed"]),
            _kpi("Средний чек", current["average_check"], previous["average_check"], "money"),
            _kpi("Отмены", current["cancel_rate"], previous["cancel_rate"], "percent"),
            _kpi("Брони", current["reservations"], previous["reservations"]),
            _kpi("Неявки по броням", current["no_show_rate"], previous["no_show_rate"], "percent"),
        ],
        "revenue": revenue,
        "hourly": hourly,
        "top_dishes": [
            {**row, "share": float(row["revenue"] / top_max * 100) if top_max else 0} for row in top
        ],
        # Для Chart.js — только числа и строки
        "chart_data": {
            "revenue": {
                "labels": [f"{row['date']:%d.%m}" for row in revenue],
                "values": [float(row["revenue"]) for row in revenue],
                "orders": [row["orders"] for row in revenue],
            },
            "hourly": {
                "labels": [f"{row['hour']:02d}:00" for row in hourly],
                "values": [row["orders"] for row in hourly],
            },
        },
    }
    return render(request, "analytics/dashboard.html", context)


def _kpi(label: str, current, previous, kind: str = "number") -> dict:
    """Плитка с цифрой и изменением к такому же прошлому периоду.

    Для долей (отмены, неявки) изменение — в процентных пунктах, а не в процентах:
    «с 10% до 12%» это +2 п.п., а не +20%.
    """
    if kind == "percent":
        delta = (current - previous) * 100
        change = f"{delta:+.1f} п.п." if previous or current else None
    elif previous:
        change = f"{(Decimal(current) - Decimal(previous)) / Decimal(previous) * 100:+.0f}%"
    else:
        change = None
    return {"label": label, "value": current, "kind": kind, "change": change}


def _errors(errors) -> list[str]:
    if isinstance(errors, dict):
        return [message for value in errors.values() for message in _errors(value)]
    if isinstance(errors, list):
        return [str(message) for message in errors]
    return [str(errors)]
