from rest_framework import serializers

from apps.tables.models import Table
from apps.tables.services import table_menu_url


class TableSerializer(serializers.ModelSerializer):
    zone_display = serializers.CharField(source="get_zone_display", read_only=True)
    menu_url = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = (
            "id",
            "number",
            "capacity",
            "zone",
            "zone_display",
            "is_active",
            "qr_token",
            "menu_url",
        )
        read_only_fields = ("id", "qr_token")

    def get_menu_url(self, obj: Table) -> str:
        return table_menu_url(obj)


class PublicTableSerializer(serializers.ModelSerializer):
    """Что видит гость, отсканировавший QR: без id и токена."""

    zone_display = serializers.CharField(source="get_zone_display", read_only=True)

    class Meta:
        model = Table
        fields = ("number", "capacity", "zone", "zone_display")
