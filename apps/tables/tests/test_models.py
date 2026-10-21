import pytest
from django.db import IntegrityError

from apps.tables.services import table_menu_url
from apps.tables.tests.factories import TableFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("capacity", [0, 21])
def test_capacity_constraint(capacity):
    with pytest.raises(IntegrityError):
        TableFactory(capacity=capacity)


def test_menu_url_uses_token_not_number(settings):
    settings.SITE_URL = "https://bahor.uz/"
    table = TableFactory(number=5)

    url = table_menu_url(table)

    assert url == f"https://bahor.uz/t/{table.qr_token}/"
    assert "/5/" not in url
