from rest_framework import serializers

from apps.reservations.models import Reservation
from apps.reservations.services import STAFF_STATUSES
from apps.users.validators import phone_validator


class ReservationCreateSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    guests_count = serializers.IntegerField(min_value=1, max_value=20)
    guest_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, validators=[phone_validator])
    email = serializers.EmailField(required=False, allow_blank=True)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ReservationSerializer(serializers.ModelSerializer):
    table_number = serializers.IntegerField(source="table.number", read_only=True)
    zone_display = serializers.CharField(source="table.get_zone_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Reservation
        fields = (
            "id",
            "token",
            "table_number",
            "zone_display",
            "guest_name",
            "phone",
            "email",
            "guests_count",
            "start_at",
            "end_at",
            "status",
            "status_display",
            "comment",
            "is_cancellable",
            "created_at",
        )
        read_only_fields = fields


class AvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField()
    guests = serializers.IntegerField(min_value=1, max_value=20)


class AvailabilitySerializer(serializers.Serializer):
    date = serializers.DateField()
    guests = serializers.IntegerField()
    slots = serializers.ListField(child=serializers.CharField(), help_text="Время в формате HH:MM")


VISIT_STATUS_CHOICES = [(status.value, status.label) for status in STAFF_STATUSES]


class ReservationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=VISIT_STATUS_CHOICES)
