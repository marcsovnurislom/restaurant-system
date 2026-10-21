from rest_framework.permissions import BasePermission

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


IsStaffMember = role_required(*User.STAFF_ROLES)
