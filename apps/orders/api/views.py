from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.errors import to_api_error
from apps.orders.api.filters import OrderFilter
from apps.orders.api.serializers import (
    OrderCreateSerializer,
    OrderSerializer,
    OrderTransitionSerializer,
)
from apps.orders.rules import OrderError
from apps.orders.selectors import order_list_for, order_queryset
from apps.orders.services import order_cancel_by_customer, order_create, order_transition
from apps.users.permissions import IsStaffMember


@extend_schema(tags=["orders"])
class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filterset_class = OrderFilter
    ordering_fields = ("created_at", "total")

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        if self.action in ("list", "transition"):
            return [IsStaffMember()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "orders"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return order_list_for(self.request.user)

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderSerializer})
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            order = order_create(
                items=[(item["dish"].pk, item["quantity"]) for item in data["items"]],
                order_type=data["type"],
                customer_name=data["customer_name"],
                phone=data["phone"],
                payment_method=data["payment_method"],
                address=data.get("address", ""),
                comment=data.get("comment", ""),
                table=data.get("table_token"),
                user=request.user if request.user.is_authenticated else None,
            )
        except OrderError as exc:
            raise to_api_error(exc) from exc
        order = order_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def my(self, request: Request) -> Response:
        """Мои заказы (для персонала тоже только свои)."""
        orders = self.filter_queryset(order_queryset().filter(user=request.user))
        page = self.paginate_queryset(orders)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(request=OrderTransitionSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request: Request, pk: str | None = None) -> Response:
        """Сменить статус заказа. Права роли проверяет state machine (orders/rules.py)."""
        serializer = OrderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = order_transition(
                order=self.get_object(),
                to_status=serializer.validated_data["status"],
                by_user=request.user,
            )
        except OrderError as exc:
            raise to_api_error(exc) from exc
        return Response(self.get_serializer(order_queryset().get(pk=order.pk)).data)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        """Гость отменяет свой заказ, пока его не приняли в работу."""
        order = self.get_object()
        if order.user_id != request.user.pk:
            raise NotFound
        try:
            order = order_cancel_by_customer(order=order)
        except OrderError as exc:
            raise to_api_error(exc) from exc
        return Response(self.get_serializer(order_queryset().get(pk=order.pk)).data)


@extend_schema(tags=["orders"])
class OrderByTokenView(generics.RetrieveAPIView):
    """Заказ по секретной ссылке — для гостя без аккаунта."""

    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = OrderSerializer
    lookup_field = "token"

    def get_queryset(self):
        return order_queryset()


@extend_schema(tags=["orders"], request=None, responses=OrderSerializer)
class OrderCancelByTokenView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(parameters=[OpenApiParameter("token", str, OpenApiParameter.PATH)])
    def post(self, request: Request, token) -> Response:
        order = get_object_or_404(order_queryset(), token=token)
        try:
            order = order_cancel_by_customer(order=order)
        except OrderError as exc:
            raise to_api_error(exc) from exc
        return Response(OrderSerializer(order_queryset().get(pk=order.pk)).data)
