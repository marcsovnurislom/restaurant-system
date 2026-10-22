from rest_framework import serializers

from apps.analytics.selectors import Period

DEFAULT_DAYS = 30
MAX_DAYS = 366


class PeriodSerializer(serializers.Serializer):
    """?date_from=2026-10-01&date_to=2026-10-31. По умолчанию — последние 30 дней."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs: dict) -> dict:
        default = Period.last_days(DEFAULT_DAYS)
        date_to = attrs.get("date_to", default.date_to)
        date_from = attrs.get("date_from", date_to - (default.date_to - default.date_from))
        if date_from > date_to:
            raise serializers.ValidationError("date_from должна быть не позже date_to.")
        if (date_to - date_from).days + 1 > MAX_DAYS:
            raise serializers.ValidationError(f"Период не длиннее {MAX_DAYS} дней.")
        attrs["period"] = Period(date_from, date_to)
        return attrs


class SummarySerializer(serializers.Serializer):
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    orders_completed = serializers.IntegerField()
    average_check = serializers.DecimalField(max_digits=14, decimal_places=2)
    cancel_rate = serializers.FloatField(help_text="Доля отменённых заказов, 0–1")
    reservations = serializers.IntegerField()
    no_show_rate = serializers.FloatField(help_text="Доля неявок среди завершённых броней, 0–1")


class SummaryResponseSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    current = SummarySerializer()
    previous = SummarySerializer(help_text="Такой же по длине период перед текущим")


class RevenueDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    orders = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)


class TopDishSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    dish_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)


class HourlyLoadSerializer(serializers.Serializer):
    hour = serializers.IntegerField()
    orders = serializers.IntegerField()
