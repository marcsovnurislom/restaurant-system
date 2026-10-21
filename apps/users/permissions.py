from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.users.models import User


class HasRole(BasePermission):
    """Пускает только аутентифицированных пользователей с одной из ролей `roles`."""

    roles: tuple[str, ...] = ()
    message = "Недостаточно прав для этого действия."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.has_role(*self.roles))


def role_required(*roles: str) -> type[HasRole]:
    """Создаёт класс permission для DRF.

    Пример: permission_classes = (role_required(User.Role.COOK, User.Role.MANAGER),)
    """
    name = "Has" + "Or".join(role.title() for role in roles) + "Role"
    return type(name, (HasRole,), {"roles": roles})


def read_only_or(*roles: str) -> type[BasePermission]:
    """Читать могут все (включая анонимов), изменять — только `roles`.

    Пример: меню видят гости, а редактирует только менеджер.
    """
    write_permission = role_required(*roles)

    class ReadOnlyOrRole(BasePermission):
        message = HasRole.message

        def has_permission(self, request, view) -> bool:
            if request.method in SAFE_METHODS:
                return True
            return write_permission().has_permission(request, view)

    ReadOnlyOrRole.__name__ = "ReadOnlyOr" + write_permission.__name__
    return ReadOnlyOrRole


IsStaffMember = role_required(*User.STAFF_ROLES)
