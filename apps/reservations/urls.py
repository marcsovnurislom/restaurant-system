from django.urls import path

from apps.reservations import views

app_name = "reservations"

urlpatterns = [
    path("new/", views.reservation_create_view, name="create"),
    path("<uuid:token>/", views.reservation_detail_view, name="detail"),
    path("<uuid:token>/cancel/", views.reservation_cancel_view, name="cancel"),
]
