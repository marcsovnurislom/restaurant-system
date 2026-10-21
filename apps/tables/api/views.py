from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.tables.api.serializers import PublicTableSerializer, TableSerializer
from apps.tables.models import Table
from apps.tables.services import table_qr_png, table_regenerate_qr
from apps.users.models import User
from apps.users.permissions import role_required

CanViewTables = role_required(User.Role.MANAGER, User.Role.WAITER)
CanManageTables = role_required(User.Role.MANAGER)


@extend_schema(tags=["tables"])
class TableViewSet(viewsets.ModelViewSet):
    """Столы видят менеджер и официанты, изменяет только менеджер."""

    queryset = Table.objects.all()
    serializer_class = TableSerializer
    pagination_class = None
    filterset_fields = ("zone", "is_active")
    ordering_fields = ("number", "capacity")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanViewTables()]
        return [CanManageTables()]

    @extend_schema(responses={(200, "image/png"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def qr(self, request: Request, pk: str | None = None) -> HttpResponse:
        """PNG с QR-кодом для печати на стол."""
        table = self.get_object()
        response = HttpResponse(table_qr_png(table), content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="table-{table.number}-qr.png"'
        return response

    @extend_schema(request=None, responses=TableSerializer)
    @action(detail=True, methods=["post"], url_path="regenerate-qr")
    def regenerate_qr(self, request: Request, pk: str | None = None) -> Response:
        """Новый токен: старые наклейки с QR перестают работать."""
        table = table_regenerate_qr(self.get_object())
        return Response(self.get_serializer(table).data)


@extend_schema(tags=["tables"])
class PublicTableView(generics.RetrieveAPIView):
    """Стол по токену из QR-кода. Нужен фронтенду или мобильному приложению гостя."""

    permission_classes = (AllowAny,)
    serializer_class = PublicTableSerializer
    queryset = Table.objects.filter(is_active=True)
    lookup_field = "qr_token"
    lookup_url_kwarg = "token"
