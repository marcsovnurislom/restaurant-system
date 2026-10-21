import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.users.models import User
from apps.users.permissions import IsStaffMember, role_required
from apps.users.tests.factories import UserFactory

KitchenPermission = role_required(User.Role.COOK, User.Role.MANAGER)


def _request_as(user):
    request = APIRequestFactory().get("/")
    request.user = user
    return request


def test_anonymous_is_denied():
    assert not KitchenPermission().has_permission(_request_as(AnonymousUser()), view=None)


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (User.Role.COOK, True),
        (User.Role.MANAGER, True),
        (User.Role.ADMIN, True),
        (User.Role.WAITER, False),
        (User.Role.CUSTOMER, False),
    ],
)
def test_role_required(role, allowed):
    request = _request_as(UserFactory.build(role=role))

    assert KitchenPermission().has_permission(request, view=None) is allowed


def test_generated_class_name_is_readable():
    assert KitchenPermission.__name__ == "HasCookOrManagerRole"


def test_customer_is_not_staff_member():
    request = _request_as(UserFactory.build(role=User.Role.CUSTOMER))

    assert not IsStaffMember().has_permission(request, view=None)
