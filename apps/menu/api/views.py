from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response

from apps.menu.api.filters import DishFilter
from apps.menu.api.serializers import (
    CategorySerializer,
    DishAvailabilitySerializer,
    DishSerializer,
    TagSerializer,
)
from apps.menu.selectors import category_list, dish_list, tag_list
from apps.menu.services import dish_set_availability
from apps.users.models import User
from apps.users.permissions import read_only_or, role_required

ManagerOrReadOnly = read_only_or(User.Role.MANAGER)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Объект используется и не может быть удалён."
    default_code = "conflict"


class MenuViewSetMixin:
    """Общее для ресурсов меню: поиск по slug и защита от удаления связанных объектов."""

    lookup_field = "slug"
    permission_classes = (ManagerOrReadOnly,)
    protected_message = Conflict.default_detail

    def is_staff_request(self) -> bool:
        user = self.request.user
        return user.is_authenticated and user.is_staff_member

    def perform_destroy(self, instance) -> None:
        # on_delete=PROTECT бросает ProtectedError; без обработки это был бы ответ 500
        try:
            instance.delete()
        except ProtectedError as exc:
            raise Conflict(self.protected_message) from exc


@extend_schema(tags=["menu"])
class CategoryViewSet(MenuViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    pagination_class = None
    protected_message = "В категории есть блюда. Сначала перенеси или удали их."

    def get_queryset(self):
        return category_list(include_inactive=self.is_staff_request())


@extend_schema(tags=["menu"])
class TagViewSet(MenuViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TagSerializer
    pagination_class = None

    def get_queryset(self):
        return tag_list()


@extend_schema(tags=["menu"])
class DishViewSet(MenuViewSetMixin, viewsets.ModelViewSet):
    """Гости видят только доступные блюда, персонал — всё меню, включая стоп-лист."""

    serializer_class = DishSerializer
    filterset_class = DishFilter
    search_fields = ("name", "description")
    ordering_fields = ("price", "name", "created_at")
    protected_message = "Блюдо есть в заказах. Поставь его в стоп-лист вместо удаления."

    def get_queryset(self):
        return dish_list(include_unavailable=self.is_staff_request())

    @extend_schema(request=DishAvailabilitySerializer, responses=DishSerializer)
    @action(
        detail=True,
        methods=["patch"],
        permission_classes=(role_required(User.Role.COOK, User.Role.MANAGER),),
    )
    def availability(self, request: Request, slug: str | None = None) -> Response:
        """Стоп-лист: повар отмечает, что блюдо закончилось."""
        serializer = DishAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dish = dish_set_availability(
            dish=self.get_object(), is_available=serializer.validated_data["is_available"]
        )
        return Response(self.get_serializer(dish).data)
