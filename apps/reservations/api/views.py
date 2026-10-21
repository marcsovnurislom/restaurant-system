from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.errors import to_api_error
from apps.reservations.api.filters import ReservationFilter
from apps.reservations.api.serializers import (
    AvailabilityQuerySerializer,
    AvailabilitySerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    ReservationStatusSerializer,
)
from apps.reservations.models import Reservation
from apps.reservations.rules import ReservationError
from apps.reservations.selectors import available_slots, reservation_list_for
from apps.reservations.services import (
    reservation_cancel,
    reservation_create,
    reservation_set_status,
)
from apps.users.models import User
from apps.users.permissions import role_required

CanManageReservations = role_required(User.Role.MANAGER, User.Role.WAITER)


@extend_schema(tags=["reservations"])
class ReservationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReservationSerializer
    filterset_class = ReservationFilter
    ordering_fields = ("start_at", "created_at")

    def get_permissions(self):
        if self.action in ("create", "availability"):
            return [AllowAny()]
        if self.action in ("list", "set_status"):
            return [CanManageReservations()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "reservations"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return reservation_list_for(self.request.user)

    @extend_schema(request=ReservationCreateSerializer, responses={201: ReservationSerializer})
    def create(self, request: Request, *args, **kwargs) -> Response:
        """Бронь создаётся сразу подтверждённой, стол подбирается автоматически."""
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        try:
            reservation = reservation_create(**serializer.validated_data, user=user)
        except ReservationError as exc:
            raise to_api_error(exc) from exc
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[AvailabilityQuerySerializer],
        responses=AvailabilitySerializer,
    )
    @action(detail=False, methods=["get"])
    def availability(self, request: Request) -> Response:
        """Свободное время на день для компании из N гостей."""
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        day, guests = query.validated_data["date"], query.validated_data["guests"]
        slots = available_slots(day=day, guests_count=guests)
        data = {
            "date": day,
            "guests": guests,
            "slots": [f"{timezone.localtime(slot):%H:%M}" for slot in slots],
        }
        return Response(AvailabilitySerializer(data).data)

    @action(detail=False, methods=["get"])
    def my(self, request: Request) -> Response:
        """Мои брони (для персонала тоже только свои, все брони — в общем списке)."""
        reservations = self.filter_queryset(
            Reservation.objects.filter(user=request.user).select_related("table")
        )
        page = self.paginate_queryset(reservations)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        # get_object ищет в reservation_list_for: чужую бронь гость не найдёт (404)
        try:
            reservation = reservation_cancel(reservation=self.get_object())
        except ReservationError as exc:
            raise to_api_error(exc) from exc
        return Response(self.get_serializer(reservation).data)

    @extend_schema(request=ReservationStatusSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request: Request, pk: str | None = None) -> Response:
        """Официант отмечает, пришёл ли гость."""
        serializer = ReservationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reservation = reservation_set_status(
                reservation=self.get_object(), status=serializer.validated_data["status"]
            )
        except ReservationError as exc:
            raise to_api_error(exc) from exc
        return Response(self.get_serializer(reservation).data)


@extend_schema(tags=["reservations"])
class ReservationByTokenView(generics.RetrieveAPIView):
    """Бронь по секретной ссылке — для гостя без аккаунта."""

    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = ReservationSerializer
    queryset = Reservation.objects.select_related("table")
    lookup_field = "token"


@extend_schema(tags=["reservations"], request=None, responses=ReservationSerializer)
class ReservationCancelByTokenView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(parameters=[OpenApiParameter("token", str, OpenApiParameter.PATH)])
    def post(self, request: Request, token) -> Response:
        reservation = get_object_or_404(Reservation.objects.select_related("table"), token=token)
        try:
            reservation = reservation_cancel(reservation=reservation)
        except ReservationError as exc:
            raise to_api_error(exc) from exc
        return Response(ReservationSerializer(reservation).data)
