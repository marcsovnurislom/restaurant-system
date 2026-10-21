from django_filters import rest_framework as filters

from apps.reservations.models import Reservation


class ReservationFilter(filters.FilterSet):
    """?date=2026-10-25&status=confirmed&table=5"""

    date = filters.DateFilter(field_name="start_at", lookup_expr="date")
    table = filters.NumberFilter(field_name="table__number")

    class Meta:
        model = Reservation
        fields = ("date", "status", "table")
