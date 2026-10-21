from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.tables.api.views import PublicTableView, TableViewSet

app_name = "tables"

router = SimpleRouter()
router.register("", TableViewSet, basename="table")

urlpatterns = [
    path("by-qr/<uuid:token>/", PublicTableView.as_view(), name="table-by-qr"),
    *router.urls,
]
