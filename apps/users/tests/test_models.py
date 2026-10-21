import pytest
from django.db import IntegrityError

from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_new_user_is_customer_by_default():
    user = User.objects.create_user(username="guest", email="guest@example.com", password="x")

    assert user.role == User.Role.CUSTOMER
    assert not user.is_staff_member


def test_createsuperuser_gets_admin_role():
    admin = User.objects.create_superuser(username="boss", email="boss@example.com", password="x")

    assert admin.role == User.Role.ADMIN
    assert admin.is_staff_member


def test_email_must_be_unique():
    UserFactory(email="same@example.com")

    with pytest.raises(IntegrityError):
        UserFactory(email="same@example.com")


@pytest.mark.parametrize(
    ("role", "checked_roles", "expected"),
    [
        (User.Role.COOK, (User.Role.COOK,), True),
        (User.Role.COOK, (User.Role.COOK, User.Role.MANAGER), True),
        (User.Role.WAITER, (User.Role.COOK,), False),
        (User.Role.CUSTOMER, (User.Role.COOK,), False),
        (User.Role.ADMIN, (User.Role.COOK,), True),
    ],
)
def test_has_role(role, checked_roles, expected):
    user = UserFactory.build(role=role)

    assert user.has_role(*checked_roles) is expected


def test_superuser_passes_any_role_check():
    user = UserFactory.build(role=User.Role.CUSTOMER, is_superuser=True)

    assert user.has_role(User.Role.COOK)


@pytest.mark.parametrize("role", sorted(User.STAFF_ROLES))
def test_staff_roles_are_staff_members(role):
    assert UserFactory.build(role=role).is_staff_member
