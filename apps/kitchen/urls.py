from django.contrib.auth import views as auth_views
from django.urls import path

from apps.kitchen import views

app_name = "kitchen"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="kitchen/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("kitchen/", views.board, name="board"),
    path("kitchen/orders/", views.snapshot, name="snapshot"),
]
