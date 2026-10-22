from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics import selectors
from apps.analytics.api.serializers import (
    HourlyLoadSerializer,
    PeriodSerializer,
    RevenueDaySerializer,
    SummaryResponseSerializer,
    TopDishSerializer,
)
from apps.analytics.selectors import Period
from apps.users.models import User
from apps.users.permissions import role_required


class AnalyticsView(APIView):
    """Отчёты видят только менеджер и администратор."""

    permission_classes = (role_required(User.Role.MANAGER),)

    def period(self, request: Request) -> Period:
        serializer = PeriodSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["period"]


@extend_schema(
    tags=["analytics"], parameters=[PeriodSerializer], responses=SummaryResponseSerializer
)
class SummaryView(AnalyticsView):
    def get(self, request: Request) -> Response:
        period = self.period(request)
        data = {
            "date_from": period.date_from,
            "date_to": period.date_to,
            "current": selectors.summary(period),
            "previous": selectors.summary(period.previous()),
        }
        return Response(SummaryResponseSerializer(data).data)


@extend_schema(
    tags=["analytics"], parameters=[PeriodSerializer], responses=RevenueDaySerializer(many=True)
)
class RevenueByDayView(AnalyticsView):
    def get(self, request: Request) -> Response:
        rows = selectors.revenue_by_day(self.period(request))
        return Response(RevenueDaySerializer(rows, many=True).data)


@extend_schema(
    tags=["analytics"], parameters=[PeriodSerializer], responses=TopDishSerializer(many=True)
)
class TopDishesView(AnalyticsView):
    def get(self, request: Request) -> Response:
        rows = selectors.top_dishes(self.period(request))
        return Response(TopDishSerializer(rows, many=True).data)


@extend_schema(
    tags=["analytics"], parameters=[PeriodSerializer], responses=HourlyLoadSerializer(many=True)
)
class HourlyLoadView(AnalyticsView):
    def get(self, request: Request) -> Response:
        rows = selectors.hourly_load(self.period(request))
        return Response(HourlyLoadSerializer(rows, many=True).data)
