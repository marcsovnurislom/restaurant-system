from django.urls import path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.api.views import LoginView, MeView, RegisterView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", LoginView.as_view(), name="token_obtain"),
    path(
        "token/refresh/",
        extend_schema_view(post=extend_schema(tags=["auth"]))(TokenRefreshView).as_view(),
        name="token_refresh",
    ),
    path("me/", MeView.as_view(), name="me"),
]
