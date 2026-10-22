from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.tests.factories import make_order
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ENDPOINTS = ["summary", "revenue-by-day", "top-dishes", "hourly-load"]
DASHBOARD_URL = reverse("analytics:dashboard")


def completed_order() -> Order:
    order = make_order()
    Order.objects.filter(pk=order.pk).update(status=Order.Status.COMPLETED)
    return order


class TestApi:
    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    @pytest.mark.parametrize(
        ("role", "expected"),
        [(User.Role.MANAGER, 200), (User.Role.ADMIN, 200), (User.Role.COOK, 403)],
    )
    def test_permissions(self, client_for, endpoint, role, expected):
        response = client_for(role).get(reverse(f"analytics-api:{endpoint}"))

        assert response.status_code == expected

    def test_anonymous(self, api_client):
        assert api_client.get(reverse("analytics-api:summary")).status_code == 401

    def test_summary_with_previous_period(self, client_for):
        completed_order()

        data = client_for(User.Role.MANAGER).get(reverse("analytics-api:summary")).data

        assert data["current"]["orders_completed"] == 1
        assert data["current"]["revenue"] == "30000.00"
        assert data["previous"]["orders_completed"] == 0

    def test_default_period_is_30_days(self, client_for):
        data = client_for(User.Role.MANAGER).get(reverse("analytics-api:revenue-by-day")).data

        assert len(data) == 30
        assert data[-1]["date"] == timezone.localdate().isoformat()

    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "2026-10-10", "date_to": "2026-10-01"},
            {"date_from": "2024-01-01", "date_to": "2026-01-01"},
            {"date_from": "вчера"},
        ],
        ids=["reversed", "too-long", "not-a-date"],
    )
    def test_invalid_period(self, client_for, params):
        response = client_for(User.Role.MANAGER).get(reverse("analytics-api:summary"), params)

        assert response.status_code == 400

    def test_custom_period(self, client_for):
        today = timezone.localdate()
        params = {
            "date_from": (today - timedelta(days=6)).isoformat(),
            "date_to": today.isoformat(),
        }

        data = client_for(User.Role.MANAGER).get(reverse("analytics-api:hourly-load"), params).data

        assert len(data) == 24


class TestDashboard:
    def test_manager_sees_dashboard(self, client):
        completed_order()
        client.force_login(UserFactory(role=User.Role.MANAGER))

        response = client.get(DASHBOARD_URL)

        html = response.content.decode()
        assert response.status_code == 200
        assert 'id="revenue-chart"' in html
        assert 'id="chart-data"' in html
        assert response.context["kpis"][1]["value"] == 1

    def test_cook_is_forbidden(self, client):
        client.force_login(UserFactory(role=User.Role.COOK))

        assert client.get(DASHBOARD_URL).status_code == 403

    def test_anonymous_goes_to_login(self, client):
        assert client.get(DASHBOARD_URL).status_code == 302

    def test_invalid_period_falls_back_with_message(self, client):
        client.force_login(UserFactory(role=User.Role.MANAGER))

        response = client.get(DASHBOARD_URL, {"date_from": "2026-10-10", "date_to": "2026-10-01"})

        assert response.status_code == 200
        assert response.context["period"].days == 30
        assert "date_from должна быть не позже date_to" in response.content.decode()

    def test_percent_change_in_points(self):
        from apps.analytics.views import _kpi

        kpi = _kpi("Отмены", 0.12, 0.10, "percent")

        assert kpi["change"] == "+2.0 п.п."

    def test_nav_link_for_manager_only(self, client):
        client.force_login(UserFactory(role=User.Role.COOK))
        assert "Аналитика" not in client.get(reverse("menu:home")).content.decode()

        client.force_login(UserFactory(role=User.Role.MANAGER))
        assert "Аналитика" in client.get(reverse("menu:home")).content.decode()
