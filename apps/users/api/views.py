from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.users.api.serializers import RegisterSerializer, UserSerializer
from apps.users.services import user_create


class RegisterView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth"

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer}, tags=["auth"])
    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = user_create(**serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["auth"])
class LoginView(TokenObtainPairView):
    """Выдаёт пару access/refresh токенов. Лимит запросов защищает от перебора паролей."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth"


@extend_schema(tags=["auth"])
class MeView(generics.RetrieveUpdateAPIView):
    """Профиль текущего пользователя. Роль и email изменить нельзя."""

    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
