from apps.users.models import User


def user_create(
    *,
    username: str,
    email: str,
    password: str,
    phone: str = "",
    first_name: str = "",
    last_name: str = "",
) -> User:
    """Регистрирует гостя.

    Роль всегда `customer`: сотрудников создаёт только администратор,
    иначе любой мог бы зарегистрироваться как менеджер.
    """
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.CUSTOMER,
    )
