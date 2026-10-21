from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.orders.api.views import OrderByTokenView, OrderCancelByTokenView, OrderViewSet

app_name = "orders-api"

router = SimpleRouter()
router.register("", OrderViewSet, basename="order")

urlpatterns = [
    path("by-token/<uuid:token>/", OrderByTokenView.as_view(), name="by-token"),
    path("by-token/<uuid:token>/cancel/", OrderCancelByTokenView.as_view(), name="by-token-cancel"),
    *router.urls,
]
