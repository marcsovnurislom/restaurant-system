import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errors import to_api_error
from apps.orders.models import Order
from apps.payments.providers import InvalidWebhook, UnknownProvider
from apps.payments.services import PaymentError, payment_process_webhook, payment_start

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["payments"],
    request=None,
    responses=inline_serializer("Checkout", {"redirect_url": serializers.CharField()}),
    parameters=[OpenApiParameter("token", str, OpenApiParameter.PATH)],
)
class CheckoutView(APIView):
    """Начать онлайн-оплату заказа. Клиент перенаправляет гостя на redirect_url."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request, token) -> Response:
        order = get_object_or_404(Order, token=token)
        try:
            session = payment_start(order=order)
        except PaymentError as exc:
            raise to_api_error(exc) from exc
        return Response({"redirect_url": session.redirect_url}, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["payments"],
    request=None,
    responses={200: None},
    parameters=[OpenApiParameter("provider", str, OpenApiParameter.PATH)],
)
class WebhookView(APIView):
    """Уведомления платёжной системы. Доверяем только проверенной подписи."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request, provider: str) -> Response:
        try:
            payment_process_webhook(
                provider_name=provider, body=request.body, headers=request.headers
            )
        except UnknownProvider:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except InvalidWebhook as exc:
            logger.warning("Отклонён webhook %s: %s", provider, exc)
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response({"received": True})
