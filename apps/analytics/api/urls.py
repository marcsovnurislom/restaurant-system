from django.urls import path

from apps.analytics.api import views

app_name = "analytics-api"

urlpatterns = [
    path("summary/", views.SummaryView.as_view(), name="summary"),
    path("revenue-by-day/", views.RevenueByDayView.as_view(), name="revenue-by-day"),
    path("top-dishes/", views.TopDishesView.as_view(), name="top-dishes"),
    path("hourly-load/", views.HourlyLoadView.as_view(), name="hourly-load"),
]
