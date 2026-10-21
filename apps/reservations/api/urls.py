from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.reservations.api.views import (
    ReservationByTokenView,
    ReservationCancelByTokenView,
    ReservationViewSet,
)

app_name = "reservations-api"

router = SimpleRouter()
router.register("", ReservationViewSet, basename="reservation")

urlpatterns = [
    path("by-token/<uuid:token>/", ReservationByTokenView.as_view(), name="by-token"),
    path(
        "by-token/<uuid:token>/cancel/",
        ReservationCancelByTokenView.as_view(),
        name="by-token-cancel",
    ),
    *router.urls,
]
