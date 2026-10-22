from django.contrib.auth import views as auth_views
from django.urls import path

from apps.kitchen import views

app_name = "kitchen"

urlpatterns = [
    path("login/", views.StaffLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("kitchen/", views.board, name="board"),
    path("kitchen/orders/", views.snapshot, name="snapshot"),
]
