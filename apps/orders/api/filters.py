from django_filters import rest_framework as filters

from apps.orders.models import Order


class OrderFilter(filters.FilterSet):
    """?status=cooking&type=delivery&date=2026-10-25"""

    date = filters.DateFilter(field_name="created_at", lookup_expr="date")

    class Meta:
        model = Order
        fields = ("status", "type", "payment_status", "date")
